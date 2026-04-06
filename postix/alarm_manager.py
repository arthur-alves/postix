"""Alarm checker + audio playback via GStreamer with subprocess fallback."""
import os
import subprocess
from datetime import datetime, timedelta

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib

from . import database as db

# ── GStreamer ──────────────────────────────────────────────────────────────────
_HAS_GST = False
try:
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
    Gst.init(None)
    _HAS_GST = True
except Exception:
    pass

# ── libnotify ─────────────────────────────────────────────────────────────────
_HAS_NOTIFY = False
try:
    gi.require_version("Notify", "0.7")
    from gi.repository import Notify
    Notify.init("Postix")
    _HAS_NOTIFY = True
except Exception:
    pass

# ── default sound candidates ───────────────────────────────────────────────────
_DEFAULT_SOUNDS = [
    "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
    "/usr/share/sounds/freedesktop/stereo/message.oga",
    "/usr/share/sounds/ubuntu/stereo/dialog-warning.ogg",
    "/usr/share/sounds/gnome/default/alerts/sonar.ogg",
]
_FALLBACK_PLAYERS = ["paplay", "aplay", "ffplay", "mpg123"]

# Keep references so GStreamer players aren't GC'd before finishing
_active_players: list = []


def _play_file(path: str):
    if not path or not os.path.exists(path):
        return
    if _HAS_GST:
        try:
            player = Gst.ElementFactory.make("playbin", None)
            player.set_property("uri", f"file://{path}")
            player.set_state(Gst.State.PLAYING)
            _active_players.append(player)

            def _cleanup():
                try:
                    player.set_state(Gst.State.NULL)
                    if player in _active_players:
                        _active_players.remove(player)
                except Exception:
                    pass
                return False

            GLib.timeout_add_seconds(30, _cleanup)
            return
        except Exception:
            pass

    # Subprocess fallback
    ext = os.path.splitext(path)[1].lower()
    for cmd in _FALLBACK_PLAYERS:
        try:
            subprocess.Popen(
                [cmd, path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except (FileNotFoundError, OSError):
            continue


def play_alarm_sound(sound_path: str | None):
    """Play custom sound if valid, otherwise fall back to system default."""
    if sound_path and os.path.exists(sound_path):
        _play_file(sound_path)
        return
    for sf in _DEFAULT_SOUNDS:
        if os.path.exists(sf):
            _play_file(sf)
            return


def _notify(title: str, body: str, sound_path: str | None):
    play_alarm_sound(sound_path)
    if _HAS_NOTIFY:
        try:
            n = Notify.Notification.new(title, body, "dialog-warning")
            n.set_urgency(Notify.Urgency.CRITICAL)
            n.show()
        except Exception:
            pass


def check_alarms(*_args):
    now = datetime.now()
    minute_start = now.replace(second=0, microsecond=0)
    minute_end   = minute_start + timedelta(minutes=1)

    for alarm in db.get_all_enabled_alarms():
        triggered  = False
        atype      = alarm["alarm_type"]
        sound_path = alarm.get("sound_path")

        if atype == "once":
            raw = alarm.get("once_datetime")
            if raw:
                try:
                    alarm_dt = datetime.strptime(raw, "%Y-%m-%d %H:%M")
                    if minute_start <= alarm_dt < minute_end:
                        last = alarm.get("last_triggered")
                        if not last or datetime.strptime(
                            last, "%Y-%m-%d %H:%M:%S"
                        ) < alarm_dt:
                            triggered = True
                            db.disable_alarm(alarm["id"])
                except ValueError:
                    pass

        elif atype == "daily":
            raw = alarm.get("daily_time")
            if raw:
                try:
                    h, m = map(int, raw.split(":"))
                    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    if minute_start <= target < minute_end:
                        last = alarm.get("last_triggered")
                        if not last or datetime.strptime(
                            last, "%Y-%m-%d %H:%M:%S"
                        ) < target:
                            triggered = True
                except ValueError:
                    pass

        elif atype == "interval":
            mins = alarm.get("interval_minutes") or 0
            if mins > 0:
                last = alarm.get("last_triggered")
                if not last:
                    db.update_alarm_last_triggered(alarm["id"])
                else:
                    try:
                        last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
                        if now >= last_dt + timedelta(minutes=mins):
                            triggered = True
                    except ValueError:
                        pass

        if triggered:
            content = (alarm.get("content") or "").strip()
            preview = content[:100] + ("…" if len(content) > 100 else "")
            _notify("🔔 Postix — Lembrete",
                    preview or "(nota sem conteúdo)",
                    sound_path)
            db.update_alarm_last_triggered(alarm["id"])

    return True


def start(interval_seconds: int = 60):
    GLib.timeout_add_seconds(interval_seconds, check_alarms)
    GLib.timeout_add_seconds(3, check_alarms)

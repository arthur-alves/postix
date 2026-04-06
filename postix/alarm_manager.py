"""Alarm checker that runs on a GLib timer."""
import os
import subprocess
from datetime import datetime, timedelta

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib

from . import database as db

try:
    gi.require_version("Notify", "0.7")
    from gi.repository import Notify
    Notify.init("Postix")
    _HAS_NOTIFY = True
except Exception:
    _HAS_NOTIFY = False

# Candidate sound files (freedesktop / ubuntu)
_SOUNDS = [
    "/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
    "/usr/share/sounds/ubuntu/stereo/dialog-warning.ogg",
    "/usr/share/sounds/gnome/default/alerts/sonar.ogg",
    "/usr/share/sounds/freedesktop/stereo/message.oga",
]
_PLAYERS = ["paplay", "aplay", "mplayer", "mpg123"]


def _play_sound():
    for sf in _SOUNDS:
        if os.path.exists(sf):
            for player in _PLAYERS:
                try:
                    subprocess.Popen(
                        [player, sf],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return
                except (FileNotFoundError, OSError):
                    continue


def _notify(title: str, body: str):
    _play_sound()
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
    minute_end = minute_start + timedelta(minutes=1)

    for alarm in db.get_all_enabled_alarms():
        triggered = False
        atype = alarm["alarm_type"]

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
                    # Start the clock — first fire is after `mins` from creation
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
            _notify("🔔 Postix — Lembrete", preview or "(nota sem conteúdo)")
            db.update_alarm_last_triggered(alarm["id"])

    return True  # keep the GLib timer running


def start(interval_seconds: int = 60):
    """Start the periodic alarm checker."""
    GLib.timeout_add_seconds(interval_seconds, check_alarms)
    # Run once after 3 s so interval alarms initialise last_triggered quickly
    GLib.timeout_add_seconds(3, check_alarms)

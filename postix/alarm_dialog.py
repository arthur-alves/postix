"""Dialog for configuring a note alarm, including custom sound selection."""
import os
from datetime import date

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio

from . import database as db

# ── sound validation ───────────────────────────────────────────────────────────
MAX_SOUND_BYTES  = 15 * 1024 * 1024   # 15 MB
ALLOWED_EXTS     = {".mp3", ".wav", ".ogg"}
ALLOWED_MIMES    = {"audio/mpeg", "audio/wav", "audio/x-wav",
                    "audio/ogg", "audio/vorbis", "application/ogg"}

# Magic bytes to confirm real audio format regardless of extension
_MAGIC = [
    (b"ID3",     "mp3"),
    (b"\xff\xfb","mp3"),
    (b"\xff\xf3","mp3"),
    (b"\xff\xf2","mp3"),
    (b"RIFF",    "wav"),   # will also check bytes[8:12] == b"WAVE"
    (b"OggS",    "ogg"),
]


def validate_sound_file(path: str) -> str | None:
    """Return None if valid, or an error message string."""
    if not os.path.isfile(path):
        return "Arquivo não encontrado."

    ext = os.path.splitext(path)[1].lower()
    if ext not in ALLOWED_EXTS:
        return f"Formato não suportado: '{ext}'.\nUse MP3, WAV ou OGG."

    size = os.path.getsize(path)
    if size == 0:
        return "O arquivo está vazio."
    if size > MAX_SOUND_BYTES:
        mb = size / (1024 * 1024)
        return f"Arquivo muito grande: {mb:.1f} MB.\nO limite é 15 MB."

    # Magic bytes check
    try:
        with open(path, "rb") as f:
            header = f.read(12)
    except OSError as e:
        return f"Não foi possível ler o arquivo:\n{e}"

    matched = False
    for magic, fmt in _MAGIC:
        if header.startswith(magic):
            if fmt == "wav" and header[8:12] != b"WAVE":
                continue   # RIFF but not WAVE
            matched = True
            break

    if not matched:
        return (
            "O arquivo não parece ser um áudio válido.\n"
            "Verifique se é realmente MP3, WAV ou OGG."
        )

    return None   # OK


# ── dialog ────────────────────────────────────────────────────────────────────

class AlarmDialog(Gtk.Dialog):

    def __init__(self, parent, note_id: int):
        super().__init__(
            title="Alarme",
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self.note_id   = note_id
        self.alarm_data = None
        self._sound_path: str | None = None   # currently selected custom sound

        self.add_buttons(
            "_Cancelar", Gtk.ResponseType.CANCEL,
            "_Salvar",   Gtk.ResponseType.OK,
        )
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_default_size(360, 400)

        self._delete_btn = self.add_button("🗑 Excluir alarme", Gtk.ResponseType.REJECT)
        self._delete_btn.set_no_show_all(True)

        self._build_ui()
        self._load_existing()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        box = self.get_content_area()
        box.set_spacing(10)
        box.set_border_width(14)

        # Enable checkbox
        self.enable_check = Gtk.CheckButton(label="Alarme ativo")
        self.enable_check.set_active(True)
        box.pack_start(self.enable_check, False, False, 0)

        box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                       False, False, 0)

        # Alarm type radios
        type_box = Gtk.Box(spacing=8)
        lbl = Gtk.Label(label="Tipo:")
        lbl.set_xalign(0)
        type_box.pack_start(lbl, False, False, 0)

        self.radio_once     = Gtk.RadioButton.new_with_label(None, "Uma vez")
        self.radio_daily    = Gtk.RadioButton.new_with_label_from_widget(
            self.radio_once, "Todo dia")
        self.radio_interval = Gtk.RadioButton.new_with_label_from_widget(
            self.radio_once, "Intervalo")

        for r in (self.radio_once, self.radio_daily, self.radio_interval):
            type_box.pack_start(r, False, False, 0)
        box.pack_start(type_box, False, False, 0)

        # Stack (per type)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(self._page_once(),     "once")
        self.stack.add_named(self._page_daily(),    "daily")
        self.stack.add_named(self._page_interval(), "interval")
        box.pack_start(self.stack, False, False, 0)

        self.radio_once.connect(    "toggled", self._on_radio, "once")
        self.radio_daily.connect(   "toggled", self._on_radio, "daily")
        self.radio_interval.connect("toggled", self._on_radio, "interval")

        box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                       False, False, 0)

        # Sound section
        box.pack_start(self._build_sound_section(), False, False, 0)

        box.show_all()

    def _page_once(self):
        g = Gtk.Grid(column_spacing=8, row_spacing=8, border_width=4)
        g.attach(Gtk.Label(label="Data (AAAA-MM-DD):"), 0, 0, 1, 1)
        self.once_date = Gtk.Entry()
        self.once_date.set_text(date.today().strftime("%Y-%m-%d"))
        g.attach(self.once_date, 1, 0, 1, 1)
        g.attach(Gtk.Label(label="Hora (HH:MM):"), 0, 1, 1, 1)
        self.once_time = Gtk.Entry()
        self.once_time.set_text("09:00")
        g.attach(self.once_time, 1, 1, 1, 1)
        return g

    def _page_daily(self):
        g = Gtk.Grid(column_spacing=8, row_spacing=8, border_width=4)
        g.attach(Gtk.Label(label="Hora (HH:MM):"), 0, 0, 1, 1)
        self.daily_time = Gtk.Entry()
        self.daily_time.set_text("08:00")
        g.attach(self.daily_time, 1, 0, 1, 1)
        note = Gtk.Label(label="Dispara todos os dias neste horário.")
        note.set_xalign(0)
        g.attach(note, 0, 1, 2, 1)
        return g

    def _page_interval(self):
        g = Gtk.Grid(column_spacing=8, row_spacing=8, border_width=4)
        g.attach(Gtk.Label(label="Repetir a cada:"), 0, 0, 1, 1)
        hb = Gtk.Box(spacing=4)
        self.interval_hours = Gtk.SpinButton.new_with_range(0, 23, 1)
        self.interval_hours.set_value(1)
        hb.pack_start(self.interval_hours, False, False, 0)
        hb.pack_start(Gtk.Label(label="h"), False, False, 0)
        self.interval_mins = Gtk.SpinButton.new_with_range(0, 59, 5)
        self.interval_mins.set_value(0)
        hb.pack_start(self.interval_mins, False, False, 0)
        hb.pack_start(Gtk.Label(label="min"), False, False, 0)
        g.attach(hb, 1, 0, 1, 1)
        return g

    def _build_sound_section(self) -> Gtk.Widget:
        frame_lbl = Gtk.Label()
        frame_lbl.set_markup("<b>Som do alarme</b>")
        frame_lbl.set_xalign(0)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.pack_start(frame_lbl, False, False, 0)

        # Radio: default / custom
        self._snd_default = Gtk.RadioButton.new_with_label(None, "Som padrão do sistema")
        self._snd_custom  = Gtk.RadioButton.new_with_label_from_widget(
            self._snd_default, "Som personalizado")
        vbox.pack_start(self._snd_default, False, False, 0)
        vbox.pack_start(self._snd_custom,  False, False, 0)

        # Custom sound row
        self._custom_row = Gtk.Box(spacing=6)
        self._custom_row.set_margin_start(20)

        self._sound_lbl = Gtk.Label(label="Nenhum arquivo selecionado")
        self._sound_lbl.set_xalign(0)
        self._sound_lbl.set_ellipsize(3)   # PANGO_ELLIPSIZE_END
        self._sound_lbl.set_hexpand(True)

        choose_btn = Gtk.Button(label="Escolher…")
        choose_btn.connect("clicked", self._on_choose_sound)

        preview_btn = Gtk.Button(label="▶")
        preview_btn.set_tooltip_text("Ouvir prévia")
        preview_btn.connect("clicked", self._on_preview_sound)

        self._custom_row.pack_start(self._sound_lbl,  True,  True,  0)
        self._custom_row.pack_start(choose_btn,        False, False, 0)
        self._custom_row.pack_start(preview_btn,       False, False, 0)
        vbox.pack_start(self._custom_row, False, False, 0)

        hint = Gtk.Label(label="Formatos aceitos: MP3, WAV, OGG  •  Máx. 15 MB")
        hint.set_xalign(0)
        hint.get_style_context().add_class("dim-label")
        hint.set_margin_start(20)
        vbox.pack_start(hint, False, False, 0)

        # Wire sensitivity
        self._snd_custom.connect("toggled", self._on_snd_radio_toggled)
        self._custom_row.set_sensitive(False)

        return vbox

    # ── event handlers ────────────────────────────────────────────────────────

    def _on_radio(self, btn, name):
        if btn.get_active():
            self.stack.set_visible_child_name(name)

    def _on_snd_radio_toggled(self, btn):
        self._custom_row.set_sensitive(btn.get_active())

    def _on_choose_sound(self, _btn):
        dlg = Gtk.FileChooserDialog(
            title="Escolher som do alarme",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dlg.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN,   Gtk.ResponseType.OK,
        )

        # File filters
        f_audio = Gtk.FileFilter()
        f_audio.set_name("Áudio (MP3, WAV, OGG)")
        for pat in ("*.mp3", "*.MP3", "*.wav", "*.WAV", "*.ogg", "*.OGG"):
            f_audio.add_pattern(pat)
        dlg.add_filter(f_audio)

        f_all = Gtk.FileFilter()
        f_all.set_name("Todos os arquivos")
        f_all.add_pattern("*")
        dlg.add_filter(f_all)

        if self._sound_path:
            dlg.set_filename(self._sound_path)

        resp = dlg.run()
        path = dlg.get_filename()
        dlg.destroy()

        if resp != Gtk.ResponseType.OK or not path:
            return

        err = validate_sound_file(path)
        if err:
            self._show_error("Arquivo inválido", err)
            return

        self._sound_path = path
        self._sound_lbl.set_text(os.path.basename(path))
        self._sound_lbl.set_tooltip_text(path)

    def _on_preview_sound(self, _btn):
        if not self._sound_path:
            return
        from .alarm_manager import play_alarm_sound
        play_alarm_sound(self._sound_path)

    def _show_error(self, title: str, msg: str):
        edlg = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title,
        )
        edlg.format_secondary_text(msg)
        edlg.run()
        edlg.destroy()

    # ── load / save ───────────────────────────────────────────────────────────

    def _load_existing(self):
        alarms = db.get_alarms_for_note(self.note_id)
        if not alarms:
            self.stack.set_visible_child_name("once")
            return

        self.alarm_data = alarms[0]
        a = self.alarm_data
        self.enable_check.set_active(bool(a.get("enabled", 1)))
        self._delete_btn.show()

        atype = a.get("alarm_type", "once")
        if atype == "once":
            self.radio_once.set_active(True)
            self.stack.set_visible_child_name("once")
            raw = a.get("once_datetime") or ""
            if " " in raw:
                d, t = raw.split(" ", 1)
                self.once_date.set_text(d)
                self.once_time.set_text(t)
        elif atype == "daily":
            self.radio_daily.set_active(True)
            self.stack.set_visible_child_name("daily")
            self.daily_time.set_text(a.get("daily_time") or "08:00")
        elif atype == "interval":
            self.radio_interval.set_active(True)
            self.stack.set_visible_child_name("interval")
            mins = int(a.get("interval_minutes") or 60)
            self.interval_hours.set_value(mins // 60)
            self.interval_mins.set_value(mins % 60)

        # Sound
        sp = a.get("sound_path")
        if sp and os.path.exists(sp):
            self._sound_path = sp
            self._snd_custom.set_active(True)
            self._custom_row.set_sensitive(True)
            self._sound_lbl.set_text(os.path.basename(sp))
            self._sound_lbl.set_tooltip_text(sp)

    def get_alarm_data(self) -> dict:
        enabled = 1 if self.enable_check.get_active() else 0
        sound   = self._sound_path if self._snd_custom.get_active() else None

        if self.radio_once.get_active():
            return {
                "alarm_type":       "once",
                "once_datetime":    f"{self.once_date.get_text()} {self.once_time.get_text()}",
                "daily_time":       None,
                "interval_minutes": None,
                "enabled":          enabled,
                "sound_path":       sound,
            }
        elif self.radio_daily.get_active():
            return {
                "alarm_type":       "daily",
                "once_datetime":    None,
                "daily_time":       self.daily_time.get_text(),
                "interval_minutes": None,
                "enabled":          enabled,
                "sound_path":       sound,
            }
        else:
            hours = int(self.interval_hours.get_value())
            mins  = int(self.interval_mins.get_value())
            return {
                "alarm_type":       "interval",
                "once_datetime":    None,
                "daily_time":       None,
                "interval_minutes": hours * 60 + mins or 60,
                "enabled":          enabled,
                "sound_path":       sound,
            }

    def get_existing_alarm_id(self):
        return self.alarm_data["id"] if self.alarm_data else None

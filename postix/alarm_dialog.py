"""Dialog for configuring a note alarm."""
from datetime import date, datetime

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from . import database as db

_CSS = b"""
.alarm-dialog {
    background-color: #FFFDF0;
}
.section-label {
    font-weight: bold;
    color: #555500;
}
"""


class AlarmDialog(Gtk.Dialog):
    """Configure / create / delete an alarm for a note."""

    def __init__(self, parent, note_id: int):
        super().__init__(
            title="Alarme",
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self.note_id = note_id
        self.alarm_data = None  # loaded below

        # Apply CSS
        provider = Gtk.CssProvider()
        provider.load_from_data(_CSS)
        self.get_style_context().add_provider(
            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.add_buttons(
            "_Cancelar", Gtk.ResponseType.CANCEL,
            "_Salvar",   Gtk.ResponseType.OK,
        )
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_default_size(340, 320)

        # Delete button (only shown when editing existing alarm)
        self._delete_btn = self.add_button("🗑 Excluir alarme", Gtk.ResponseType.REJECT)
        self._delete_btn.set_no_show_all(True)

        self._build_ui()
        self._load_existing()

    # ------------------------------------------------------------------
    def _build_ui(self):
        box = self.get_content_area()
        box.set_spacing(10)
        box.set_border_width(14)

        # --- Enable / disable toggle ---
        self.enable_check = Gtk.CheckButton(label="Alarme ativo")
        self.enable_check.set_active(True)
        box.pack_start(self.enable_check, False, False, 0)

        box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                       False, False, 0)

        # --- Type selection ---
        type_box = Gtk.Box(spacing=6)
        lbl = Gtk.Label(label="Tipo:")
        lbl.get_style_context().add_class("section-label")
        type_box.pack_start(lbl, False, False, 0)

        self.radio_once     = Gtk.RadioButton.new_with_label(None, "Uma vez")
        self.radio_daily    = Gtk.RadioButton.new_with_label_from_widget(
            self.radio_once, "Todo dia")
        self.radio_interval = Gtk.RadioButton.new_with_label_from_widget(
            self.radio_once, "Intervalo")

        for r in (self.radio_once, self.radio_daily, self.radio_interval):
            type_box.pack_start(r, False, False, 0)
        box.pack_start(type_box, False, False, 0)

        # --- Stack (one page per type) ---
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self.stack.add_named(self._build_once_page(),     "once")
        self.stack.add_named(self._build_daily_page(),    "daily")
        self.stack.add_named(self._build_interval_page(), "interval")

        box.pack_start(self.stack, True, True, 0)

        # Wire radio toggling
        self.radio_once.connect(    "toggled", self._on_radio, "once")
        self.radio_daily.connect(   "toggled", self._on_radio, "daily")
        self.radio_interval.connect("toggled", self._on_radio, "interval")

        box.show_all()

    def _build_once_page(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=8, border_width=8)

        grid.attach(Gtk.Label(label="Data (AAAA-MM-DD):"), 0, 0, 1, 1)
        self.once_date = Gtk.Entry()
        self.once_date.set_placeholder_text("2025-12-31")
        self.once_date.set_text(date.today().strftime("%Y-%m-%d"))
        grid.attach(self.once_date, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label="Hora (HH:MM):"), 0, 1, 1, 1)
        self.once_time = Gtk.Entry()
        self.once_time.set_placeholder_text("09:00")
        self.once_time.set_text("09:00")
        grid.attach(self.once_time, 1, 1, 1, 1)

        return grid

    def _build_daily_page(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=8, border_width=8)

        grid.attach(Gtk.Label(label="Hora (HH:MM):"), 0, 0, 1, 1)
        self.daily_time = Gtk.Entry()
        self.daily_time.set_placeholder_text("08:00")
        self.daily_time.set_text("08:00")
        grid.attach(self.daily_time, 1, 0, 1, 1)

        note = Gtk.Label(label="Disparará todos os dias neste horário.")
        note.set_line_wrap(True)
        note.set_xalign(0)
        grid.attach(note, 0, 1, 2, 1)

        return grid

    def _build_interval_page(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=8, border_width=8)

        grid.attach(Gtk.Label(label="Repetir a cada:"), 0, 0, 1, 1)

        hbox = Gtk.Box(spacing=4)
        self.interval_hours = Gtk.SpinButton.new_with_range(0, 23, 1)
        self.interval_hours.set_value(1)
        hbox.pack_start(self.interval_hours, False, False, 0)
        hbox.pack_start(Gtk.Label(label="h"), False, False, 0)

        self.interval_mins = Gtk.SpinButton.new_with_range(0, 59, 5)
        self.interval_mins.set_value(0)
        hbox.pack_start(self.interval_mins, False, False, 0)
        hbox.pack_start(Gtk.Label(label="min"), False, False, 0)

        grid.attach(hbox, 1, 0, 1, 1)

        note = Gtk.Label(label="Ex.: 2h 0min = alerta a cada 2 horas.")
        note.set_line_wrap(True)
        note.set_xalign(0)
        grid.attach(note, 0, 1, 2, 1)

        return grid

    # ------------------------------------------------------------------
    def _on_radio(self, btn, name):
        if btn.get_active():
            self.stack.set_visible_child_name(name)

    def _load_existing(self):
        alarms = db.get_alarms_for_note(self.note_id)
        if not alarms:
            self.stack.set_visible_child_name("once")
            return

        self.alarm_data = alarms[0]
        alarm = self.alarm_data
        self.enable_check.set_active(bool(alarm.get("enabled", 1)))
        self._delete_btn.show()

        atype = alarm.get("alarm_type", "once")
        if atype == "once":
            self.radio_once.set_active(True)
            self.stack.set_visible_child_name("once")
            raw = alarm.get("once_datetime", "") or ""
            if " " in raw:
                d, t = raw.split(" ", 1)
                self.once_date.set_text(d)
                self.once_time.set_text(t)
        elif atype == "daily":
            self.radio_daily.set_active(True)
            self.stack.set_visible_child_name("daily")
            self.daily_time.set_text(alarm.get("daily_time") or "08:00")
        elif atype == "interval":
            self.radio_interval.set_active(True)
            self.stack.set_visible_child_name("interval")
            mins = int(alarm.get("interval_minutes") or 60)
            self.interval_hours.set_value(mins // 60)
            self.interval_mins.set_value(mins % 60)

    # ------------------------------------------------------------------
    def get_alarm_data(self) -> dict:
        """Return dict suitable for db.save_alarm()."""
        enabled = 1 if self.enable_check.get_active() else 0

        if self.radio_once.get_active():
            return {
                "alarm_type":       "once",
                "once_datetime":    f"{self.once_date.get_text()} {self.once_time.get_text()}",
                "daily_time":       None,
                "interval_minutes": None,
                "enabled":          enabled,
            }
        elif self.radio_daily.get_active():
            return {
                "alarm_type":       "daily",
                "once_datetime":    None,
                "daily_time":       self.daily_time.get_text(),
                "interval_minutes": None,
                "enabled":          enabled,
            }
        else:
            hours = int(self.interval_hours.get_value())
            mins  = int(self.interval_mins.get_value())
            total = hours * 60 + mins or 60  # minimum 1 minute
            return {
                "alarm_type":       "interval",
                "once_datetime":    None,
                "daily_time":       None,
                "interval_minutes": total,
                "enabled":          enabled,
            }

    def get_existing_alarm_id(self):
        return self.alarm_data["id"] if self.alarm_data else None

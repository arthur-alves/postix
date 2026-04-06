"""Application class — manages windows, tray icon and lifecycle."""
import os
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from . import database as db
from . import alarm_manager
from .note_window import NoteWindow

# Try AppIndicator3 (Ubuntu/elementaryOS); fall back to StatusIcon
_HAS_INDICATOR = False
try:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3
    _HAS_INDICATOR = True
except (ValueError, ImportError):
    pass

_ICON_NAME = "xpad"           # preferred (xpad-style sticky note icon)
_ICON_FALLBACK = "accessories-text-editor"


class PostixApp:

    def __init__(self):
        db.init_db()
        self._windows: list[NoteWindow] = []
        self._setup_tray()
        alarm_manager.start()
        self._load_notes()
        if not self._windows:
            self.create_new_note()

    # ── window management ──────────────────────────────────────────────────────

    def _load_notes(self):
        for note in db.get_all_notes():
            win = NoteWindow(note, self)
            self._windows.append(win)

    def create_new_note(self):
        offset = len(self._windows) * 24
        x = 130 + offset
        y = 130 + offset
        note_id = db.create_note(x=x, y=y)
        note_data = {
            "id": note_id, "content": "",
            "x": x, "y": y, "width": 260, "height": 280,
            "always_on_top": 1,
        }
        win = NoteWindow(note_data, self)
        self._windows.append(win)
        return win

    def remove_window(self, win: NoteWindow):
        if win in self._windows:
            self._windows.remove(win)

    def show_all_notes(self, *_args):
        for win in self._windows:
            win.show()
            win.present()

    # ── tray / status icon ─────────────────────────────────────────────────────

    def _setup_tray(self):
        if _HAS_INDICATOR:
            self._indicator = AppIndicator3.Indicator.new(
                "postix",
                _ICON_NAME,
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
            )
            # Try preferred icon; if theme doesn't have it use fallback
            theme = Gtk.IconTheme.get_default()
            if not theme.has_icon(_ICON_NAME):
                self._indicator.set_icon_full(_ICON_FALLBACK, "Postix")
            self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            self._indicator.set_menu(self._build_tray_menu())
        else:
            self._status_icon = Gtk.StatusIcon()
            theme = Gtk.IconTheme.get_default()
            icon = _ICON_NAME if theme.has_icon(_ICON_NAME) else _ICON_FALLBACK
            self._status_icon.set_from_icon_name(icon)
            self._status_icon.set_tooltip_text("Postix — notas post-it")
            self._status_icon.connect("activate",    lambda *_: self.show_all_notes())
            self._status_icon.connect("popup-menu",  self._on_status_popup)

    def _build_tray_menu(self) -> Gtk.Menu:
        menu = Gtk.Menu()

        item_new = Gtk.MenuItem(label="✚  Novo post-it")
        item_new.connect("activate", lambda *_: self.create_new_note())
        menu.append(item_new)

        item_show = Gtk.MenuItem(label="⬆  Mostrar todos")
        item_show.connect("activate", self.show_all_notes)
        menu.append(item_show)

        menu.append(Gtk.SeparatorMenuItem())

        item_quit = Gtk.MenuItem(label="✕  Sair")
        item_quit.connect("activate", self._quit)
        menu.append(item_quit)

        menu.show_all()
        return menu

    def _on_status_popup(self, icon, button, activate_time):
        menu = self._build_tray_menu()
        menu.popup(None, None,
                   Gtk.StatusIcon.position_menu,
                   icon, button, activate_time)

    # ── lifecycle ──────────────────────────────────────────────────────────────

    def _quit(self, *_args):
        for win in list(self._windows):
            win._force_save()
        Gtk.main_quit()

    def run(self):
        Gtk.main()

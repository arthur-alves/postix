"""PostIt note window — undecorated, yellow, draggable, resizable."""
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from . import database as db
from .alarm_dialog import AlarmDialog

# ── constants ──────────────────────────────────────────────────────────────────
MIN_W       = 160
MIN_H       = 130
MAX_SIZE    = 1280
HEADER_H    = 30
GRIP_SIZE   = 14   # corner resize grip size (px)

_CSS = (
    ".postit-window {"
    "  background-color: #FFFF88;"
    "  border: 1px solid #C8B400;"
    "  border-radius: 3px;"
    "}"
    ".postit-header {"
    "  background: linear-gradient(to bottom, #F5E820, #E8D800);"
    "  border-bottom: 1px solid #C8B400;"
    "  border-radius: 3px 3px 0 0;"
    "  padding: 0 4px;"
    "  min-height: 30px;"
    "}"
    ".hdr-btn {"
    "  background: transparent;"
    "  border: none;"
    "  border-radius: 4px;"
    "  padding: 1px 4px;"
    "  min-width: 22px;"
    "  min-height: 22px;"
    "  color: #666600;"
    "  font-size: 13px;"
    "}"
    ".hdr-btn:hover  { background-color: rgba(0,0,0,0.15); }"
    ".hdr-btn:active { background-color: rgba(0,0,0,0.25); }"
    ".alarm-on  { color: #CC4400; }"
    ".alarm-off { color: #999966; }"
    "textview, textview text {"
    "  background-color: #FFFF88;"
    "  color: #333300;"
    "  font-family: 'Ubuntu','DejaVu Sans','Liberation Sans',sans-serif;"
    "  font-size: 13px;"
    "  caret-color: #333300;"
    "}"
    "textview text {"
    "  background-image: repeating-linear-gradient("
    "    transparent, transparent 21px,"
    "    #D8C800 21px, #D8C800 22px"
    "  );"
    "}"
    "scrolledwindow { background-color: #FFFF88; }"
    ".resize-grip {"
    "  background-color: transparent;"
    "  border: none;"
    "  min-width: 14px;"
    "  min-height: 14px;"
    "}"
).encode("utf-8")


class NoteWindow(Gtk.Window):
    """A single floating post-it note."""

    def __init__(self, note_data: dict, app):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.note_id: int = note_data["id"]
        self.app = app
        self._save_text_timer = None
        self._save_geo_timer  = None

        # ── apply app-wide CSS once ──
        _apply_css()

        # ── window flags ──
        self.set_decorated(False)
        self.set_resizable(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(bool(note_data.get("always_on_top", 1)))
        self.set_app_paintable(True)

        # size constraints
        geo = Gdk.Geometry()
        geo.min_width  = MIN_W
        geo.min_height = MIN_H
        geo.max_width  = MAX_SIZE
        geo.max_height = MAX_SIZE
        self.set_geometry_hints(
            None, geo,
            Gdk.WindowHints.MIN_SIZE | Gdk.WindowHints.MAX_SIZE,
        )

        self.get_style_context().add_class("postit-window")

        # ── build UI ──
        self._build_ui()

        # ── load persisted data ──
        w = max(MIN_W, min(MAX_SIZE, note_data.get("width",  260)))
        h = max(MIN_H, min(MAX_SIZE, note_data.get("height", 280)))
        self.resize(w, h)
        self.move(note_data.get("x", 120), note_data.get("y", 120))

        buf = self.text_view.get_buffer()
        buf.set_text(note_data.get("content", "") or "")

        self._update_alarm_icon()

        # ── connect window-level events (for border resize) ──
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.connect("button-press-event",  self._on_window_button_press)
        self.connect("motion-notify-event", self._on_window_motion)
        self.connect("configure-event",     self._on_configure)
        self.connect("delete-event",        self._on_delete)

        self.show_all()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root)

        root.pack_start(self._build_header(), False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_shadow_type(Gtk.ShadowType.NONE)

        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_view.set_left_margin(8)
        self.text_view.set_right_margin(8)
        self.text_view.set_top_margin(6)
        self.text_view.set_bottom_margin(6)

        buf = self.text_view.get_buffer()
        buf.connect("changed", self._on_text_changed)

        # Detect resize edges from inside the text view using screen coords
        self.text_view.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.text_view.connect("button-press-event",  self._on_tv_button_press)
        self.text_view.connect("motion-notify-event", self._on_tv_motion)

        scroll.add(self.text_view)
        root.pack_start(scroll, True, True, 0)

    def _build_header(self) -> Gtk.Widget:
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        header.get_style_context().add_class("postit-header")
        header.set_size_request(-1, HEADER_H)

        # ── drag area ──
        drag_eb = Gtk.EventBox()
        drag_eb.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        drag_eb.connect("button-press-event", self._on_header_drag)
        drag_eb.set_hexpand(True)

        drag_lbl = Gtk.Label()
        drag_lbl.set_markup('<span size="small" foreground="#888800">✎ Post-it</span>')
        drag_lbl.set_xalign(0)
        drag_lbl.set_margin_start(6)
        drag_eb.add(drag_lbl)
        header.pack_start(drag_eb, True, True, 0)

        def _btn(label, tooltip, callback, extra_class=None):
            b = Gtk.Button(label=label)
            b.get_style_context().add_class("hdr-btn")
            if extra_class:
                b.get_style_context().add_class(extra_class)
            b.set_relief(Gtk.ReliefStyle.NONE)
            b.set_tooltip_text(tooltip)
            b.connect("clicked", callback)
            return b

        # ── fechar app ──
        header.pack_end(_btn("⏻", "Fechar aplicativo", self._on_quit_app), False, False, 2)

        # ── deletar nota ──
        header.pack_end(_btn("🗑", "Deletar esta nota", self._on_delete_note), False, False, 0)

        # ── salvar ──
        header.pack_end(_btn("💾", "Salvar nota", self._on_save_clicked), False, False, 0)

        # ── separador visual ──
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.set_margin_top(6)
        sep.set_margin_bottom(6)
        header.pack_end(sep, False, False, 2)

        # ── alarme ──
        self._alarm_btn = _btn("🔕", "Configurar alarme", self._on_alarm_clicked)
        header.pack_end(self._alarm_btn, False, False, 0)

        # ── nova nota ──
        header.pack_end(_btn("+", "Novo post-it", lambda _: self.app.create_new_note()), False, False, 0)

        return header

    # ── event handlers ─────────────────────────────────────────────────────────

    def _on_header_drag(self, _widget, event):
        if event.button == 1:
            self.begin_move_drag(
                event.button, int(event.x_root), int(event.y_root), event.time
            )

    def _on_window_button_press(self, _widget, event):
        if event.button == 1:
            edge = self._detect_edge(event.x, event.y)
            if edge is not None:
                self.begin_resize_drag(
                    edge, event.button,
                    int(event.x_root), int(event.y_root), event.time,
                )

    def _on_window_motion(self, _widget, event):
        edge = self._detect_edge(event.x, event.y)
        cursor_name = _EDGE_CURSORS.get(edge, "default")
        win = self.get_window()
        if win:
            win.set_cursor(Gdk.Cursor.new_from_name(self.get_display(), cursor_name))

    def _on_tv_button_press(self, _widget, event):
        """Resize from inside the text view by converting to window coords."""
        if event.button != 1:
            return False
        wx, wy = self.get_position()
        ww, wh = self.get_size()
        # window-relative position from screen coords
        rx = event.x_root - wx
        ry = event.y_root - wy
        edge = self._detect_edge(rx, ry)
        if edge is not None:
            self.begin_resize_drag(edge, event.button,
                                   int(event.x_root), int(event.y_root), event.time)
            return True   # consume event so text view doesn't move the cursor
        return False

    def _on_tv_motion(self, _widget, event):
        """Change cursor to resize arrows when near window edges."""
        wx, wy = self.get_position()
        rx = event.x_root - wx
        ry = event.y_root - wy
        edge = self._detect_edge(rx, ry)
        cursor_name = _EDGE_CURSORS.get(edge, "text")
        win = self.get_window()
        if win:
            win.set_cursor(Gdk.Cursor.new_from_name(self.get_display(), cursor_name))

    def _detect_edge(self, x, y):
        """Return Gdk.WindowEdge if (x,y) is within GRIP_SIZE of a border."""
        w, h = self.get_size()
        b = GRIP_SIZE
        right  = x >= w - b
        bottom = y >= h - b
        left   = x <= b
        top    = y <= b and y > HEADER_H  # don't overlap header drag area

        if bottom and right:  return Gdk.WindowEdge.SOUTH_EAST
        if bottom and left:   return Gdk.WindowEdge.SOUTH_WEST
        if top    and right:  return Gdk.WindowEdge.NORTH_EAST
        if top    and left:   return Gdk.WindowEdge.NORTH_WEST
        if right:             return Gdk.WindowEdge.EAST
        if bottom:            return Gdk.WindowEdge.SOUTH
        if left:              return Gdk.WindowEdge.WEST
        if top:               return Gdk.WindowEdge.NORTH
        return None

    def _on_text_changed(self, _buf):
        if self._save_text_timer:
            GLib.source_remove(self._save_text_timer)
        self._save_text_timer = GLib.timeout_add(1000, self._flush_text)

    def _flush_text(self):
        buf = self.text_view.get_buffer()
        start, end = buf.get_bounds()
        db.update_note(self.note_id, content=buf.get_text(start, end, True))
        self._save_text_timer = None
        return False

    def _on_configure(self, _widget, _event):
        if self._save_geo_timer:
            GLib.source_remove(self._save_geo_timer)
        self._save_geo_timer = GLib.timeout_add(600, self._flush_geo)

    def _flush_geo(self):
        x, y = self.get_position()
        w, h = self.get_size()
        db.update_note(self.note_id, x=x, y=y, width=w, height=h)
        self._save_geo_timer = None
        return False

    def _on_alarm_clicked(self, _btn):
        dlg = AlarmDialog(self, self.note_id)
        response = dlg.run()

        if response == Gtk.ResponseType.OK:
            data = dlg.get_alarm_data()
            aid  = dlg.get_existing_alarm_id()
            db.save_alarm(
                aid, self.note_id,
                data["alarm_type"], data["once_datetime"],
                data["daily_time"], data["interval_minutes"],
                data["enabled"],
            )
            self._update_alarm_icon()

        elif response == Gtk.ResponseType.REJECT:
            aid = dlg.get_existing_alarm_id()
            if aid:
                db.delete_alarm(aid)
            self._update_alarm_icon()

        dlg.destroy()

    def _update_alarm_icon(self):
        alarms = db.get_alarms_for_note(self.note_id)
        active = any(a["enabled"] for a in alarms)
        self._alarm_btn.set_label("🔔" if active else "🔕")
        ctx = self._alarm_btn.get_style_context()
        ctx.remove_class("alarm-on")
        ctx.remove_class("alarm-off")
        ctx.add_class("alarm-on" if active else "alarm-off")
        tip = "Alarme ativo — clique para editar" if active else "Configurar alarme"
        self._alarm_btn.set_tooltip_text(tip)

    def _on_save_clicked(self, _btn):
        self._force_save()
        # Brief visual feedback: flash the button label
        btn = _btn
        btn.set_label("✓")
        GLib.timeout_add(800, lambda: btn.set_label("💾") or False)

    def _on_delete_note(self, _btn):
        dlg = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Deletar esta nota?",
        )
        dlg.format_secondary_text("Esta ação não pode ser desfeita.")
        dlg.set_default_response(Gtk.ResponseType.NO)
        response = dlg.run()
        dlg.destroy()
        if response == Gtk.ResponseType.YES:
            self._force_save()
            db.delete_note(self.note_id)
            self.app.remove_window(self)
            self.destroy()

    def _on_quit_app(self, _btn):
        self.app._quit()

    def _on_delete(self, _widget, _event):
        # WM close — apenas ignora (janela sem decoração, não deve ocorrer)
        return True

    # ── public helpers ─────────────────────────────────────────────────────────

    def _force_save(self):
        if self._save_text_timer:
            GLib.source_remove(self._save_text_timer)
            self._flush_text()
        if self._save_geo_timer:
            GLib.source_remove(self._save_geo_timer)
            self._flush_geo()


# ── module-level helpers ───────────────────────────────────────────────────────

_css_applied = False

def _apply_css():
    global _css_applied
    if _css_applied:
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(_CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    _css_applied = True


_EDGE_CURSORS = {
    Gdk.WindowEdge.SOUTH_EAST: "se-resize",
    Gdk.WindowEdge.SOUTH_WEST: "sw-resize",
    Gdk.WindowEdge.NORTH_EAST: "ne-resize",
    Gdk.WindowEdge.NORTH_WEST: "nw-resize",
    Gdk.WindowEdge.EAST:       "e-resize",
    Gdk.WindowEdge.SOUTH:      "s-resize",
    Gdk.WindowEdge.WEST:       "w-resize",
    Gdk.WindowEdge.NORTH:      "n-resize",
}

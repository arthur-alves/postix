"""PostIt note window — colors, markdown preview, image support."""
import shutil
import uuid
from pathlib import Path
from urllib.parse import unquote

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib

from . import database as db
from .alarm_dialog import AlarmDialog

# ── optional webkit2 ───────────────────────────────────────────────────────────
_HAS_WEBKIT = False
_WebKit2 = None
for _wkv in ("4.1", "4.0"):
    try:
        gi.require_version("WebKit2", _wkv)
        from gi.repository import WebKit2 as _WebKit2
        _HAS_WEBKIT = True
        break
    except (ValueError, ImportError):
        continue

# ── optional markdown module ───────────────────────────────────────────────────
try:
    import markdown as _md
    def _to_html(text):
        return _md.markdown(
            text,
            extensions=["fenced_code", "tables", "nl2br", "sane_lists"],
        )
    _HAS_MD = True
except ImportError:
    import html as _html
    def _to_html(text):
        return "<pre style='white-space:pre-wrap'>" + _html.escape(text) + "</pre>"
    _HAS_MD = False

# ── constants ──────────────────────────────────────────────────────────────────
MIN_W      = 220
MIN_H      = 140
MAX_SIZE   = 1280
HEADER_H   = 30
GRIP       = 14
IMAGES_DIR = Path.home() / ".local" / "share" / "postix" / "images"

# 6 post-it color palettes  (bg, header, border, line)
NOTE_COLORS = [
    {"key": "yellow", "label": "Amarelo", "bg": "#FFFF88",
     "hdr": "#F0E020", "border": "#C8B400", "line": "#D8C800"},
    {"key": "pink",   "label": "Rosa",    "bg": "#FFD1DC",
     "hdr": "#FFB3C6", "border": "#E06080", "line": "#F0A0B8"},
    {"key": "blue",   "label": "Azul",    "bg": "#C8E6FF",
     "hdr": "#A0CFFF", "border": "#4A90D0", "line": "#90C0F0"},
    {"key": "green",  "label": "Verde",   "bg": "#C8F0C8",
     "hdr": "#A0E0A0", "border": "#40A040", "line": "#90D090"},
    {"key": "orange", "label": "Laranja", "bg": "#FFE0B0",
     "hdr": "#FFC880", "border": "#D08020", "line": "#F0C070"},
    {"key": "purple", "label": "Lilás",   "bg": "#E8D0FF",
     "hdr": "#D0A8FF", "border": "#8050C0", "line": "#C090F0"},
]
COLOR_BY_KEY = {c["key"]: c for c in NOTE_COLORS}
DEFAULT_COLOR = NOTE_COLORS[0]

# ── base CSS (color-neutral) ───────────────────────────────────────────────────
_BASE_CSS = (
    ".postit-window {"
    "  border-radius: 3px;"
    "}"
    ".postit-header {"
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
    "  font-size: 13px;"
    "}"
    ".hdr-btn:hover  { background-color: rgba(0,0,0,0.15); }"
    ".hdr-btn:active { background-color: rgba(0,0,0,0.25); }"
    ".alarm-on  { color: #CC4400; }"
    ".alarm-off { color: #999966; }"
    "textview, textview text {"
    "  font-family: 'Ubuntu','DejaVu Sans','Liberation Sans',sans-serif;"
    "  font-size: 13px;"
    "}"
    ".color-dot {"
    "  border-radius: 50%;"
    "  border: 2px solid rgba(0,0,0,0.25);"
    "  min-width: 24px;"
    "  min-height: 24px;"
    "  padding: 0;"
    "}"
    ".color-dot:hover { border-color: rgba(0,0,0,0.6); }"
    ".color-dot-selected { border: 3px solid #000000; }"
).encode()


def _color_css(note_id: int, c: dict) -> bytes:
    """Generate per-note CSS using the window's CSS ID (#note-N)."""
    nid = f"#note-{note_id}"
    return (
        f"{nid} {{ background-color: {c['bg']}; border: 1px solid {c['border']}; }}"
        f"{nid} .postit-header {{"
        f"  background: linear-gradient(to bottom, {c['hdr']}, {c['hdr']});"
        f"  border-bottom: 1px solid {c['border']};"
        f"}}"
        f"{nid} textview, {nid} textview text {{ background-color: {c['bg']}; color: #333300; }}"
        f"{nid} textview text {{"
        f"  background-image: repeating-linear-gradient("
        f"    transparent, transparent 21px, {c['line']} 21px, {c['line']} 22px);"
        f"}}"
        f"{nid} scrolledwindow {{ background-color: {c['bg']}; }}"
    ).encode()


def _html_page(content_html: str, c: dict) -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
* {{ box-sizing: border-box; }}
body {{
  font-family: Ubuntu, 'DejaVu Sans', 'Liberation Sans', sans-serif;
  font-size: 13px;
  background: {c['bg']};
  color: #333300;
  margin: 8px 10px;
  padding: 0;
}}
img {{ max-width: 100%; height: auto; border-radius: 4px; margin: 4px 0; }}
h1,h2,h3,h4 {{ color: #555500; border-bottom: 1px solid {c['line']}; margin-top: 12px; }}
h1 {{ font-size: 1.3em; }} h2 {{ font-size: 1.15em; }} h3 {{ font-size: 1.05em; }}
code {{ background: rgba(0,0,0,0.10); padding: 1px 5px; border-radius: 3px; font-size: 0.92em; }}
pre  {{ background: rgba(0,0,0,0.08); padding: 8px; border-radius: 4px; overflow: auto; }}
pre code {{ background: none; padding: 0; }}
blockquote {{ border-left: 3px solid {c['border']}; margin: 4px 0 4px 4px;
              padding: 2px 0 2px 10px; color: #666; }}
table {{ border-collapse: collapse; width: 100%; }}
th,td {{ border: 1px solid {c['border']}; padding: 4px 8px; }}
th {{ background: {c['hdr']}; }}
a {{ color: #0066CC; }}
ul,ol {{ padding-left: 20px; }}
</style></head><body>{content_html}</body></html>"""


_css_applied = False
def _apply_base_css():
    global _css_applied
    if _css_applied:
        return
    p = Gtk.CssProvider()
    p.load_from_data(_BASE_CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), p,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    _css_applied = True


_EDGE_CURSORS = {
    Gdk.WindowEdge.SOUTH_EAST: "se-resize",
    Gdk.WindowEdge.SOUTH_WEST: "sw-resize",
    Gdk.WindowEdge.NORTH_EAST: "ne-resize",
    Gdk.WindowEdge.NORTH_WEST: "nw-resize",
    Gdk.WindowEdge.EAST:  "e-resize",
    Gdk.WindowEdge.SOUTH: "s-resize",
    Gdk.WindowEdge.WEST:  "w-resize",
    Gdk.WindowEdge.NORTH: "n-resize",
}


class NoteWindow(Gtk.Window):

    def __init__(self, note_data: dict, app):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.note_id: int = note_data["id"]
        self.app = app
        self._save_text_timer = None
        self._save_geo_timer  = None
        self._color_provider  = Gtk.CssProvider()
        self._in_preview      = False

        _apply_base_css()

        # Per-note CSS provider (for color)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            self._color_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1,
        )

        # Window identity used by per-note CSS (#note-N)
        self.set_name(f"note-{self.note_id}")

        # Window flags
        self.set_decorated(False)
        self.set_resizable(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(bool(note_data.get("always_on_top", 1)))
        self.get_style_context().add_class("postit-window")

        geo = Gdk.Geometry()
        geo.min_width  = MIN_W
        geo.min_height = MIN_H
        geo.max_width  = MAX_SIZE
        geo.max_height = MAX_SIZE
        self.set_geometry_hints(None, geo,
            Gdk.WindowHints.MIN_SIZE | Gdk.WindowHints.MAX_SIZE)

        # Images folder for this note
        self._images_dir = IMAGES_DIR / str(self.note_id)
        self._images_dir.mkdir(parents=True, exist_ok=True)

        # Load color
        color_key  = note_data.get("color", "yellow") or "yellow"
        self._color = COLOR_BY_KEY.get(color_key, DEFAULT_COLOR)

        self._build_ui()
        self._apply_color(self._color)

        # Load geometry
        w = max(MIN_W, min(MAX_SIZE, note_data.get("width",  260)))
        h = max(MIN_H, min(MAX_SIZE, note_data.get("height", 280)))
        self.resize(w, h)
        self.move(note_data.get("x", 120), note_data.get("y", 120))

        # Load content
        buf = self.text_view.get_buffer()
        buf.set_text(note_data.get("content", "") or "")

        self._update_alarm_icon()

        # Window-level resize detection (borders outside text view)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.connect("button-press-event",  self._on_win_press)
        self.connect("motion-notify-event", self._on_win_motion)
        self.connect("configure-event",     self._on_configure)
        self.connect("delete-event",        lambda *_: True)

        self.show_all()
        if _HAS_WEBKIT:
            self._preview_stack.set_visible_child_name("edit")

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root)
        root.pack_start(self._build_header(), False, False, 0)

        # Edit / Preview stack
        if _HAS_WEBKIT:
            self._preview_stack = Gtk.Stack()
            self._preview_stack.set_transition_type(
                Gtk.StackTransitionType.CROSSFADE)
            self._preview_stack.add_named(self._build_editor(), "edit")
            self._preview_stack.add_named(self._build_webview(), "preview")
            root.pack_start(self._preview_stack, True, True, 0)
        else:
            root.pack_start(self._build_editor(), True, True, 0)

    def _build_editor(self) -> Gtk.Widget:
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_shadow_type(Gtk.ShadowType.NONE)

        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_view.set_left_margin(8)
        self.text_view.set_right_margin(8)
        self.text_view.set_top_margin(6)
        self.text_view.set_bottom_margin(6)
        self.text_view.get_buffer().connect("changed", self._on_text_changed)

        # Resize from edges via text view
        self.text_view.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
        )
        self.text_view.connect("button-press-event",  self._on_tv_press)
        self.text_view.connect("motion-notify-event", self._on_tv_motion)

        # Drag & drop image files
        self.text_view.drag_dest_set(
            Gtk.DestDefaults.ALL, [], Gdk.DragAction.COPY)
        self.text_view.drag_dest_add_uri_targets()
        self.text_view.drag_dest_add_image_targets()
        self.text_view.connect("drag-data-received", self._on_drag_data)

        # Paste (intercept Ctrl+V for images)
        self.text_view.connect("paste-clipboard", self._on_paste_clipboard)

        scroll.add(self.text_view)
        return scroll

    def _build_webview(self) -> Gtk.Widget:
        settings = _WebKit2.Settings()
        settings.set_allow_file_access_from_file_urls(True)
        settings.set_allow_universal_access_from_file_urls(True)
        settings.set_javascript_can_access_clipboard(False)
        settings.set_enable_javascript(False)

        self._web_view = _WebKit2.WebView()
        self._web_view.set_settings(settings)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self._web_view)
        return scroll

    def _build_header(self) -> Gtk.Widget:
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
        header.get_style_context().add_class("postit-header")
        header.set_size_request(-1, HEADER_H)

        # Drag area
        drag_eb = Gtk.EventBox()
        drag_eb.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        drag_eb.connect("button-press-event", self._on_header_drag)
        drag_eb.set_hexpand(True)
        lbl = Gtk.Label()
        lbl.set_markup('<span size="small" foreground="#888800">✎ Post-it</span>')
        lbl.set_xalign(0)
        lbl.set_margin_start(6)
        drag_eb.add(lbl)
        header.pack_start(drag_eb, True, True, 0)

        def btn(label, tip, cb, extra=None):
            b = Gtk.Button(label=label)
            b.get_style_context().add_class("hdr-btn")
            if extra:
                b.get_style_context().add_class(extra)
            b.set_relief(Gtk.ReliefStyle.NONE)
            b.set_tooltip_text(tip)
            b.connect("clicked", cb)
            return b

        # Right-side buttons (packed end = right-to-left order)
        header.pack_end(btn("⏻", "Fechar aplicativo",  self._on_quit),        False, False, 2)
        header.pack_end(btn("🗑", "Deletar nota",       self._on_delete_note), False, False, 0)
        header.pack_end(btn("💾", "Salvar nota",        self._on_save),        False, False, 0)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.set_margin_top(6); sep.set_margin_bottom(6)
        header.pack_end(sep, False, False, 2)

        self._alarm_btn = btn("🔕", "Configurar alarme", self._on_alarm)
        header.pack_end(self._alarm_btn, False, False, 0)

        # Preview toggle (only when webkit available)
        if _HAS_WEBKIT:
            self._preview_btn = btn("👁", "Visualizar markdown", self._on_toggle_preview)
            header.pack_end(self._preview_btn, False, False, 0)

        # Color picker
        color_btn = Gtk.MenuButton()
        color_btn.set_label("🎨")
        color_btn.get_style_context().add_class("hdr-btn")
        color_btn.set_relief(Gtk.ReliefStyle.NONE)
        color_btn.set_tooltip_text("Cor do post-it")
        color_btn.set_popover(self._build_color_popover())
        header.pack_end(color_btn, False, False, 0)

        header.pack_end(btn("+", "Novo post-it", lambda _: self.app.create_new_note()), False, False, 0)

        return header

    def _build_color_popover(self) -> Gtk.Popover:
        popover = Gtk.Popover()
        grid = Gtk.Grid()
        grid.set_row_spacing(6)
        grid.set_column_spacing(6)
        grid.set_border_width(10)

        self._color_dots = {}
        for i, c in enumerate(NOTE_COLORS):
            dot = Gtk.Button()
            dot.set_tooltip_text(c["label"])
            dot.get_style_context().add_class("color-dot")
            # CSS for this specific dot color
            p = Gtk.CssProvider()
            p.load_from_data(
                f".color-dot-{c['key']} {{ background-color: {c['bg']}; }}".encode()
            )
            dot.get_style_context().add_provider(p, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 2)
            dot.get_style_context().add_class(f"color-dot-{c['key']}")
            dot.set_size_request(28, 28)
            dot.connect("clicked", self._on_color_pick, c, popover)
            grid.attach(dot, i % 3, i // 3, 1, 1)
            self._color_dots[c["key"]] = dot

        self._refresh_color_dots()
        grid.show_all()
        popover.add(grid)
        return popover

    # ── color ─────────────────────────────────────────────────────────────────

    def _apply_color(self, c: dict):
        self._color = c
        self._color_provider.load_from_data(_color_css(self.note_id, c))
        self._refresh_color_dots()
        # Update webview background if in preview
        if _HAS_WEBKIT and self._in_preview:
            self._render_preview()

    def _refresh_color_dots(self):
        if not hasattr(self, "_color_dots"):
            return
        for key, dot in self._color_dots.items():
            ctx = dot.get_style_context()
            if key == self._color["key"]:
                ctx.add_class("color-dot-selected")
            else:
                ctx.remove_class("color-dot-selected")

    def _on_color_pick(self, _btn, c: dict, popover: Gtk.Popover):
        self._apply_color(c)
        db.update_note(self.note_id, color=c["key"])
        popover.popdown()

    # ── markdown preview ───────────────────────────────────────────────────────

    def _on_toggle_preview(self, _btn):
        self._in_preview = not self._in_preview
        if self._in_preview:
            self._render_preview()
            self._preview_stack.set_visible_child_name("preview")
            self._preview_btn.set_label("✏")
            self._preview_btn.set_tooltip_text("Editar")
        else:
            self._preview_stack.set_visible_child_name("edit")
            self._preview_btn.set_label("👁")
            self._preview_btn.set_tooltip_text("Visualizar markdown")

    def _render_preview(self):
        buf = self.text_view.get_buffer()
        s, e = buf.get_bounds()
        md_text = buf.get_text(s, e, True)
        html = _html_page(_to_html(md_text), self._color)
        self._web_view.load_html(html, f"file://{self._images_dir}/")

    # ── images ────────────────────────────────────────────────────────────────

    def _save_image_pixbuf(self, pixbuf) -> str:
        """Save a GdkPixbuf to the note's images dir. Returns file:// URI."""
        fname = f"{uuid.uuid4().hex}.png"
        path  = self._images_dir / fname
        pixbuf.savev(str(path), "png", [], [])
        return f"file://{path}"

    def _insert_at_cursor(self, text: str):
        buf = self.text_view.get_buffer()
        buf.insert_at_cursor(text)

    def _on_paste_clipboard(self, widget):
        """Handle Ctrl+V: if clipboard has image, save and insert markdown."""
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        pixbuf = clipboard.wait_for_image()
        if pixbuf:
            uri = self._save_image_pixbuf(pixbuf)
            self._insert_at_cursor(f"\n![imagem]({uri})\n")
            # Stop the default paste
            GLib.idle_add(lambda: True)
            return True   # signal handled
        # Let default paste proceed (text)
        return False

    def _on_drag_data(self, widget, ctx, x, y, selection, info, time):
        uris = selection.get_uris()
        if uris:
            for uri in uris:
                path = Path(unquote(uri.replace("file://", "", 1)))
                if path.suffix.lower() in {".png",".jpg",".jpeg",".gif",".webp",".bmp",".svg"}:
                    dest = self._images_dir / f"{uuid.uuid4().hex}{path.suffix}"
                    shutil.copy2(str(path), str(dest))
                    self._insert_at_cursor(f"\n![imagem](file://{dest})\n")
            Gtk.drag_finish(ctx, True, False, time)
            return
        # Try image data directly
        pixbuf = selection.get_pixbuf()
        if pixbuf:
            uri = self._save_image_pixbuf(pixbuf)
            self._insert_at_cursor(f"\n![imagem]({uri})\n")
            Gtk.drag_finish(ctx, True, False, time)

    # ── resize / drag ─────────────────────────────────────────────────────────

    def _on_header_drag(self, _w, event):
        if event.button == 1:
            self.begin_move_drag(event.button,
                                 int(event.x_root), int(event.y_root), event.time)

    def _detect_edge(self, x, y):
        w, h = self.get_size()
        b = GRIP
        right  = x >= w - b
        bottom = y >= h - b
        left   = x <= b
        top    = b < y <= HEADER_H
        if bottom and right:  return Gdk.WindowEdge.SOUTH_EAST
        if bottom and left:   return Gdk.WindowEdge.SOUTH_WEST
        if top    and right:  return Gdk.WindowEdge.NORTH_EAST
        if top    and left:   return Gdk.WindowEdge.NORTH_WEST
        if right:             return Gdk.WindowEdge.EAST
        if bottom:            return Gdk.WindowEdge.SOUTH
        if left:              return Gdk.WindowEdge.WEST
        if top:               return Gdk.WindowEdge.NORTH
        return None

    def _on_win_press(self, _w, event):
        if event.button == 1:
            edge = self._detect_edge(event.x, event.y)
            if edge is not None:
                self.begin_resize_drag(edge, event.button,
                                       int(event.x_root), int(event.y_root), event.time)

    def _on_win_motion(self, _w, event):
        edge = self._detect_edge(event.x, event.y)
        win  = self.get_window()
        if win:
            win.set_cursor(Gdk.Cursor.new_from_name(
                self.get_display(), _EDGE_CURSORS.get(edge, "default")))

    def _on_tv_press(self, _w, event):
        if event.button != 1:
            return False
        wx, wy = self.get_position()
        edge = self._detect_edge(event.x_root - wx, event.y_root - wy)
        if edge is not None:
            self.begin_resize_drag(edge, event.button,
                                   int(event.x_root), int(event.y_root), event.time)
            return True
        return False

    def _on_tv_motion(self, _w, event):
        wx, wy = self.get_position()
        edge = self._detect_edge(event.x_root - wx, event.y_root - wy)
        win  = self.get_window()
        if win:
            win.set_cursor(Gdk.Cursor.new_from_name(
                self.get_display(), _EDGE_CURSORS.get(edge, "text")))

    # ── save / load ───────────────────────────────────────────────────────────

    def _on_text_changed(self, _buf):
        if self._save_text_timer:
            GLib.source_remove(self._save_text_timer)
        self._save_text_timer = GLib.timeout_add(1000, self._flush_text)

    def _flush_text(self):
        buf = self.text_view.get_buffer()
        s, e = buf.get_bounds()
        db.update_note(self.note_id, content=buf.get_text(s, e, True))
        self._save_text_timer = None
        return False

    def _on_configure(self, _w, _e):
        if self._save_geo_timer:
            GLib.source_remove(self._save_geo_timer)
        self._save_geo_timer = GLib.timeout_add(600, self._flush_geo)

    def _flush_geo(self):
        x, y = self.get_position()
        w, h = self.get_size()
        db.update_note(self.note_id, x=x, y=y, width=w, height=h)
        self._save_geo_timer = None
        return False

    def _force_save(self):
        if self._save_text_timer:
            GLib.source_remove(self._save_text_timer)
            self._flush_text()
        if self._save_geo_timer:
            GLib.source_remove(self._save_geo_timer)
            self._flush_geo()

    # ── button handlers ───────────────────────────────────────────────────────

    def _on_save(self, btn):
        self._force_save()
        btn.set_label("✓")
        GLib.timeout_add(800, lambda: btn.set_label("💾") or False)

    def _on_delete_note(self, _btn):
        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Deletar esta nota?",
        )
        dlg.format_secondary_text("Esta ação não pode ser desfeita.")
        dlg.set_default_response(Gtk.ResponseType.NO)
        resp = dlg.run()
        dlg.destroy()
        if resp == Gtk.ResponseType.YES:
            self._force_save()
            db.delete_note(self.note_id)
            self.app.remove_window(self)
            self.destroy()

    def _on_quit(self, _btn):
        self.app._quit()

    def _on_alarm(self, _btn):
        dlg = AlarmDialog(self, self.note_id)
        resp = dlg.run()
        if resp == Gtk.ResponseType.OK:
            data = dlg.get_alarm_data()
            aid  = dlg.get_existing_alarm_id()
            db.save_alarm(aid, self.note_id,
                          data["alarm_type"], data["once_datetime"],
                          data["daily_time"], data["interval_minutes"],
                          data["enabled"], data.get("sound_path"))
            self._update_alarm_icon()
        elif resp == Gtk.ResponseType.REJECT:
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
        self._alarm_btn.set_tooltip_text(
            "Alarme ativo — clique para editar" if active else "Configurar alarme")

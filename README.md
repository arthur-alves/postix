# Postix 📝

Floating sticky notes for the Linux desktop — lightweight, always on top, with alarm support.

![License](https://img.shields.io/badge/license-MIT-yellow)
![Platform](https://img.shields.io/badge/platform-Linux-blue)
![Python](https://img.shields.io/badge/python-3.6%2B-green)

## Features

- **Yellow post-it** floating over all windows
- **Drag** from the title bar to reposition
- **Resize** from any corner or edge (up to 1280×1280 px)
- **Multiple notes** — create as many as you need
- **Auto-save** — content and position saved automatically
- **Alarm per note** with three modes:
  - **Once** — specific date and time
  - **Daily** — every day at a fixed time (e.g. 14:00)
  - **Interval** — every N hours/minutes (e.g. every 2 h)
- **Desktop notifications** via libnotify
- **Local storage** — SQLite at `~/.local/share/postix/notes.db`
- No internet connection required

## Screenshot

> A clean yellow post-it floating on your desktop with alarm and save controls.

## Installation

### Option 1 — .deb package (Ubuntu / Debian)

Download the latest `.deb` from [Releases](../../releases) and run:

```bash
sudo dpkg -i postix_1.0.0_all.deb

# If missing dependencies:
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-notify-0.7 libnotify-bin
```

### Option 2 — Run from source

```bash
# Install dependencies
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-notify-0.7 libnotify-bin

# Clone and run
git clone https://github.com/arthur4lves/postix.git
cd postix
python3 postix/main.py
```

### Option 3 — Install from source

```bash
sudo make install
```

## Uninstall

```bash
sudo dpkg -r postix
# or, if installed from source:
sudo make uninstall
```

## Dependencies

| Package | Purpose |
|---|---|
| `python3` | Runtime |
| `python3-gi` | GTK3 Python bindings |
| `gir1.2-gtk-3.0` | GTK3 |
| `gir1.2-notify-0.7` | Desktop notifications |
| `libnotify-bin` | Notification daemon |
| `gir1.2-appindicator3-0.1` | System tray (optional, Ubuntu) |

## Build .deb from source

```bash
python3 build_deb.py
# Output: dist/postix_1.0.0_all.deb
```

## Usage

| Button | Action |
|---|---|
| `+` | New post-it |
| `🔔 / 🔕` | Configure alarm |
| `💾` | Save note |
| `🗑` | Delete note (asks for confirmation) |
| `⏻` | Quit application |

**Drag** the yellow title bar to move the note.  
**Resize** by dragging from any corner or edge.

## Data

All data is stored locally:

```
~/.local/share/postix/notes.db   ← SQLite database
```

No cloud, no telemetry, no accounts.

## License

[MIT](LICENSE) © 2026 Arthur Alves <arthur.4lvevs@gmail.com>

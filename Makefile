PREFIX ?= /usr
DESTDIR ?=

BINDIR     = $(DESTDIR)$(PREFIX)/bin
LIBDIR     = $(DESTDIR)$(PREFIX)/lib/postix
APPDIR     = $(DESTDIR)$(PREFIX)/share/applications
ICONDIR48  = $(DESTDIR)$(PREFIX)/share/icons/hicolor/48x48/apps
ICONSVG    = $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps

.PHONY: all run install uninstall deb clean

all:
	@echo "Targets: run | install | uninstall | deb | clean"

# ── run directly (dev) ──────────────────────────────────────────────────────
run:
	python3 postix/main.py

# ── system-wide install ─────────────────────────────────────────────────────
install:
	install -d $(BINDIR) $(LIBDIR) $(APPDIR) $(ICONSVG) $(ICONDIR48)
	cp -r postix $(LIBDIR)/
	@printf '#!/bin/bash\nexec python3 $(PREFIX)/lib/postix/postix/main.py "$$@"\n' \
		> $(BINDIR)/postix
	chmod 755 $(BINDIR)/postix
	install -m 644 data/postix.desktop $(APPDIR)/postix.desktop
	install -m 644 data/postix.svg     $(ICONSVG)/postix.svg
	@if command -v rsvg-convert >/dev/null 2>&1; then \
		rsvg-convert -w 48 -h 48 data/postix.svg -o $(ICONDIR48)/postix.png; \
	fi
	@gtk-update-icon-cache -f -t $(DESTDIR)$(PREFIX)/share/icons/hicolor 2>/dev/null || true
	@update-desktop-database $(APPDIR) 2>/dev/null || true
	@echo "Installed. Run: postix"

uninstall:
	rm -rf  $(LIBDIR)
	rm -f   $(BINDIR)/postix
	rm -f   $(APPDIR)/postix.desktop
	rm -f   $(ICONSVG)/postix.svg
	rm -f   $(ICONDIR48)/postix.png
	@gtk-update-icon-cache -f -t $(DESTDIR)$(PREFIX)/share/icons/hicolor 2>/dev/null || true

# ── .deb package ────────────────────────────────────────────────────────────
deb:
	python3 build_deb.py

# ── cleanup ──────────────────────────────────────────────────────────────────
clean:
	rm -rf dist/ __pycache__/ postix/__pycache__/

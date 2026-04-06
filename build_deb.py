#!/usr/bin/env python3
"""Build script: generates dist/postix_1.0.0_all.deb"""
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

VERSION = "1.0.4"
PACKAGE = f"postix_{VERSION}_all"

ROOT = Path(__file__).parent
DIST = ROOT / "dist" / PACKAGE


def step(msg):
    print(f"\033[1;34m→\033[0m {msg}")


def run(*cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)
    return result.stdout


def main():
    # ── clean ──
    if DIST.exists():
        shutil.rmtree(DIST)

    # ── directory structure ──
    dirs = [
        DIST / "DEBIAN",
        DIST / "usr/bin",
        DIST / "usr/lib/postix",
        DIST / "usr/share/applications",
        DIST / "usr/share/icons/hicolor/48x48/apps",
        DIST / "usr/share/icons/hicolor/scalable/apps",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # ── copy Python package ──
    step("Copying Python package …")
    shutil.copytree(ROOT / "postix", DIST / "usr/lib/postix/postix")

    # ── launcher script ──
    step("Creating launcher …")
    launcher = DIST / "usr/bin/postix"
    launcher.write_text(
        "#!/bin/bash\n"
        "exec python3 /usr/lib/postix/postix/main.py \"$@\"\n"
    )
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    # ── desktop file ──
    step("Copying desktop entry …")
    shutil.copy(ROOT / "data/postix.desktop",
                DIST / "usr/share/applications/postix.desktop")

    # ── icon ──
    svg_src = ROOT / "data/postix.svg"
    step("Copying SVG icon …")
    shutil.copy(svg_src, DIST / "usr/share/icons/hicolor/scalable/apps/postix.svg")

    # Try to convert SVG → PNG if rsvg-convert or inkscape is available
    png_dst = DIST / "usr/share/icons/hicolor/48x48/apps/postix.png"
    for converter, *args in (
        ("rsvg-convert", "-w", "48", "-h", "48"),
        ("inkscape",     "-w", "48", "-h", "48", "--export-type=png",
         f"--export-filename={png_dst}"),
    ):
        if shutil.which(converter):
            if converter == "rsvg-convert":
                with open(png_dst, "wb") as f:
                    r = subprocess.run(
                        [converter, *args, str(svg_src)],
                        stdout=f, stderr=subprocess.DEVNULL,
                    )
                if r.returncode == 0:
                    step("PNG icon generated via rsvg-convert.")
                    break
            else:
                r = subprocess.run(
                    [converter, str(svg_src), *args],
                    stderr=subprocess.DEVNULL,
                )
                if r.returncode == 0:
                    step("PNG icon generated via inkscape.")
                    break
    else:
        step("No SVG→PNG converter found; only SVG icon will be installed.")

    # ── DEBIAN/control ──
    step("Writing DEBIAN/control …")
    (DIST / "DEBIAN/control").write_text(
        f"Package: postix\n"
        f"Version: {VERSION}\n"
        f"Section: utils\n"
        f"Priority: optional\n"
        f"Architecture: all\n"
        f"Depends: python3 (>= 3.6), python3-gi, gir1.2-gtk-3.0, "
        f"gir1.2-notify-0.7, libnotify-bin, python3-markdown\n"
        f"Suggests: gir1.2-appindicator3-0.1, gir1.2-webkit2-4.1 | gir1.2-webkit2-4.0\n"
        f"Maintainer: Arthur Alves <arthur.4lvevs@gmail.com>\n"
        f"Description: Post-it notes for the Linux desktop\n"
        f" Floating sticky notes that stay on top of other windows.\n"
        f" Each note can be dragged, resized, and has an independent alarm\n"
        f" (one-time, daily, or repeating interval). Data is stored locally\n"
        f" in ~/.local/share/postix/notes.db (SQLite).\n"
    )

    # ── DEBIAN/postinst ──
    postinst = DIST / "DEBIAN/postinst"
    postinst.write_text(
        "#!/bin/sh\n"
        "set -e\n"
        "gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true\n"
        "update-desktop-database /usr/share/applications || true\n"
    )
    postinst.chmod(postinst.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    # ── build .deb ──
    step("Building .deb …")
    deb_path = ROOT / "dist" / f"{PACKAGE}.deb"
    run("dpkg-deb", "--build", "--root-owner-group", str(DIST), str(deb_path))

    size = deb_path.stat().st_size / 1024
    print(f"\n\033[1;32m✓ Package ready:\033[0m {deb_path}  ({size:.1f} KB)")
    print(f"\n  Install:   sudo dpkg -i {deb_path}")
    print(f"  Remove:    sudo dpkg -r postix\n")


if __name__ == "__main__":
    main()

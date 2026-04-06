#!/usr/bin/env python3
"""Postix entry point."""
import sys
import os

# Allow running directly: python3 postix/main.py
_here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _here not in sys.path:
    sys.path.insert(0, _here)

from postix.app import PostixApp


def main():
    app = PostixApp()
    app.run()


if __name__ == "__main__":
    main()

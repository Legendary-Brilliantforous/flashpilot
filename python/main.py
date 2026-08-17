#!/usr/bin/env python3
"""Entry point: launch the PyQt6 GUI."""
import sys


def main():
    from .gui import qt_app

    qt_app.main()


if __name__ == "__main__":
    # allow running as `python -m python.main`
    sys.path.insert(0, __file__.rsplit("/", 2)[0])
    main()

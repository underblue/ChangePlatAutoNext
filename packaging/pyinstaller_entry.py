"""PyInstaller entry script for the desktop application."""

from change_plate_next.interfaces.desktop.app import main


if __name__ == "__main__":
    raise SystemExit(main())

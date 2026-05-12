"""Desktop theme loading utilities."""

from __future__ import annotations

from importlib import resources

STYLE_PACKAGE = "change_plate_next.interfaces.desktop.styles"
ASSET_PACKAGE = "change_plate_next.interfaces.desktop.assets"


def load_qss(theme_name: str = "workshop_light") -> str:
    """Load a QSS theme bundled with the package."""
    resource_name = f"{theme_name}.qss"
    return resources.files(STYLE_PACKAGE).joinpath(resource_name).read_text(encoding="utf-8")


def apply_theme(app: object, theme_name: str = "workshop_light") -> None:
    """Apply a bundled QSS theme to a QApplication-like object."""
    app.setStyleSheet(load_qss(theme_name))


def app_icon_path() -> str:
    """Return the bundled application icon path."""
    return str(resources.files(ASSET_PACKAGE).joinpath("app_icon.png"))

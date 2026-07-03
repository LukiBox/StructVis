"""Settings store: merge-on-write and the cross-feature clobber regression."""
from __future__ import annotations

import json

from structvis.core import settings


def test_set_value_merges_keys():
    settings.set_value("alpha", 1)
    settings.set_value("beta", "two")
    data = settings.load()
    assert data["alpha"] == 1 and data["beta"] == "two"


def test_language_change_preserves_theme():
    """Regression: i18n._save() used to overwrite the whole settings file,
    wiping the saved theme and hide_welcome keys."""
    from structvis.core import i18n
    from structvis.ui import theme

    theme.set_theme("dark")
    settings.set_value("hide_welcome", True)
    i18n.set_language("pl")
    try:
        data = settings.load()
        assert data.get("language") == "pl"
        assert data.get("theme") == "dark", "language change wiped the theme"
        assert data.get("hide_welcome") is True
    finally:
        i18n.set_language("en")


def test_default_theme_is_dark():
    """With no saved preference the app starts in dark mode."""
    from structvis.ui import theme
    data = settings.load()
    data.pop("theme", None)
    settings._path().write_text(json.dumps(data), encoding="utf-8")
    theme._load()
    assert theme.get_theme() == "dark"

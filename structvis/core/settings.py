"""
Persistent application settings - one JSON file, merge-on-write.

Every consumer (language, theme, welcome flag) goes through set_value(), which
read-merges the existing file instead of overwriting it, so features can no
longer clobber each other's keys. STRUCTVIS_CONFIG_DIR overrides the location
(used by the test suite to avoid touching the real user config).
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def config_dir() -> Path:
    env = os.environ.get("STRUCTVIS_CONFIG_DIR")
    if env:
        return Path(env)
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "StructVis"


def _path() -> Path:
    return config_dir() / "settings.json"


def load() -> dict:
    try:
        return json.loads(_path().read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - missing/corrupt file -> defaults
        return {}


def get(key: str, default=None):
    return load().get(key, default)


def set_value(key: str, value) -> None:
    try:
        data = load()
        data[key] = value
        p = _path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001 - settings are best-effort
        pass

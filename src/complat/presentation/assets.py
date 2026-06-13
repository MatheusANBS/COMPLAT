from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def app_icon_path() -> Path | None:
    for filename in ("complat.ico", "complat.png"):
        path = _find_asset(filename)
        if path:
            return path

    return None


def app_logo_path() -> Path | None:
    return _find_asset("complat.png") or _find_asset("complat.ico")


def _find_asset(filename: str) -> Path | None:
    package_asset = files("complat.assets").joinpath(filename)
    if package_asset.is_file():
        return Path(str(package_asset))

    candidates = [
        Path.cwd() / filename,
        Path(__file__).resolve().parents[3] / filename,
    ]

    for path in candidates:
        if path.exists():
            return path

    return None

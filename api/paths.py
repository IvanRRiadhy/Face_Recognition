import os
import sys
from typing import Optional

def get_base_dir() -> str:
    """
    Returns base directory for bundled PyInstaller frozen executables or regular Python scripts.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_asset_path(relative_path: str) -> str:
    """
    Resolves an asset path whether running in development or inside a frozen PyInstaller binary.
    """
    # 1. Check next to running executable if external override exists
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidate = os.path.join(exe_dir, relative_path)
        if os.path.exists(candidate):
            return candidate

    # 2. Check in PyInstaller internal bundle or dev workspace
    return os.path.join(get_base_dir(), relative_path)


def get_config_path() -> Optional[str]:
    """
    Resolves the active config.json path.
    """
    candidate_paths = [
        os.path.join(os.getcwd(), "config.json"),
        get_asset_path("config.json"),
    ]
    for path in candidate_paths:
        if path and os.path.exists(path):
            return path
    return None


def get_config() -> dict:
    """
    Reads config.json dynamically from disk.
    """
    import json
    path = get_config_path()
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def get_preset_for_prefix(prefix: Optional[str]) -> dict:
    """
    Looks up preset configuration in config.json for a given prefix.
    Strips whitespace and surrounding quotes if present.
    """
    if not prefix:
        return {}
    clean_prefix = prefix.strip().strip("'\"")
    if not clean_prefix:
        return {}
    config = get_config()
    presets = config.get("presets")
    if isinstance(presets, dict):
        # Direct lookup or stripped lookup
        if prefix in presets and isinstance(presets[prefix], dict):
            return presets[prefix]
        if clean_prefix in presets and isinstance(presets[clean_prefix], dict):
            return presets[clean_prefix]
    return {}


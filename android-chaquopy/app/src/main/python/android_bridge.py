"""
Python-Wrapper fuer native Android-Funktionen (Chaquopy).
Nutzung:
    from android_bridge import show_toast, save_text, read_text, list_files, device_info
"""

from __future__ import annotations

try:
    from java import jclass  # type: ignore

    _Bridge = jclass("com.thilo.evocreatureai.AndroidBridge")
except Exception:  # Desktop/Fallback
    _Bridge = None


def _require_bridge() -> None:
    if _Bridge is None:
        raise RuntimeError("AndroidBridge nicht verfuegbar (nur in Android/Chaquopy).")


def show_toast(text: str) -> str:
    _require_bridge()
    return str(_Bridge.showToast(text))


def save_text(file_name: str, content: str) -> str:
    _require_bridge()
    return str(_Bridge.saveText(file_name, content))


def read_text(file_name: str) -> str:
    _require_bridge()
    return str(_Bridge.readText(file_name))


def list_files() -> list[str]:
    _require_bridge()
    raw = str(_Bridge.listFiles())
    if not raw.strip():
        return []
    return raw.splitlines()


def device_info() -> str:
    _require_bridge()
    return str(_Bridge.getDeviceInfo())

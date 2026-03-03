from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


def _human_size(num: int) -> str:
    size = float(max(0, num))
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size >= 1024 and i < len(units) - 1:
        size /= 1024.0
        i += 1
    return f"{size:.1f} {units[i]}"


def _root_path() -> Path:
    candidates = [Path("/storage/emulated/0"), Path.home(), Path.cwd()]
    for p in candidates:
        try:
            if p.exists():
                return p
        except Exception:
            continue
    return Path.cwd()


@dataclass
class Entry:
    name: str
    path: str
    is_dir: bool
    size: int


_CURRENT = _root_path()


def _safe_path(path: str | Path) -> Path:
    p = Path(str(path))
    if not p.exists():
        return _CURRENT
    return p


def _scan(path: Path) -> list[Entry]:
    out: list[Entry] = []
    try:
        for child in path.iterdir():
            try:
                is_dir = child.is_dir()
            except Exception:
                continue
            if is_dir:
                # Android: keine teure Rekursion im UI-Thread
                size = 0
            else:
                try:
                    size = child.stat().st_size
                except Exception:
                    size = 0
            out.append(Entry(child.name, str(child), is_dir, int(size)))
    except Exception:
        pass
    return out


def set_root() -> str:
    global _CURRENT
    _CURRENT = _root_path()
    return str(_CURRENT)


def set_path(path: str) -> str:
    global _CURRENT
    _CURRENT = _safe_path(path)
    return str(_CURRENT)


def go_up(path: str | None = None) -> str:
    global _CURRENT
    p = _safe_path(path or _CURRENT)
    parent = p.parent if p.parent != p else p
    _CURRENT = parent
    return str(_CURRENT)


def list_entries(path: str | None = None, query: str = "", sort_mode: str = "size") -> str:
    global _CURRENT
    p = _safe_path(path or _CURRENT)
    _CURRENT = p
    entries = _scan(p)

    q = (query or "").strip().lower()
    if q:
        entries = [e for e in entries if q in e.name.lower()]

    if sort_mode == "name":
        entries.sort(key=lambda e: e.name.lower())
    else:
        entries.sort(key=lambda e: e.size, reverse=True)

    total_size = sum(e.size for e in entries)
    payload = {
        "path": str(p),
        "status": f"{len(entries)} Einträge | Gesamt: {_human_size(total_size)}",
        "entries": [
            {
                "name": e.name,
                "path": e.path,
                "is_dir": e.is_dir,
                "size": e.size,
                "size_h": _human_size(e.size),
            }
            for e in entries
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def delete_entry(path: str) -> str:
    p = Path(path)
    try:
        if p.is_dir():
            shutil.rmtree(p)
            return f"Ordner gelöscht: {p.name}"
        p.unlink(missing_ok=True)
        return f"Datei gelöscht: {p.name}"
    except Exception as e:
        return f"Löschen fehlgeschlagen: {e}"

from __future__ import annotations

import json
from pathlib import Path

import ai_leanr_walk as core


def _android_files_dir() -> Path:
    try:
        from com.chaquo.python import Python  # type: ignore

        app = Python.getPlatform().getApplication()
        return Path(str(app.getFilesDir().getAbsolutePath()))
    except Exception:
        return Path.cwd() / "android_data"


STATE_DIR = _android_files_dir() / "ai_lern_walk"
STATE_FILE = STATE_DIR / "spezial_state.json"


def _save_state() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    s = core._ANDROID.state
    data = {
        "generation": s.generation,
        "best_ever": s.best_ever,
        "last_best": s.last_best,
        "survivors": s.survivors,
        "culled": s.culled,
        "mut_rate": s.mut_rate,
        "mut_std": s.mut_std,
    }
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_state() -> None:
    if not STATE_FILE.exists():
        return
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return

    s = core._ANDROID.state
    s.generation = int(data.get("generation", s.generation))
    s.best_ever = float(data.get("best_ever", s.best_ever))
    s.last_best = float(data.get("last_best", s.last_best))
    s.survivors = int(data.get("survivors", s.survivors))
    s.culled = int(data.get("culled", s.culled))
    s.mut_rate = float(data.get("mut_rate", s.mut_rate))
    s.mut_std = float(data.get("mut_std", s.mut_std))


def get_status() -> str:
    base = core.get_status()
    return f"{base}\nModus: Android Spezial\nState: {STATE_FILE}"


def run_epoch() -> str:
    result = core.run_epoch()
    _save_state()
    return f"{result}\nModus: Android Spezial (gespeichert)"


def reset_training() -> str:
    core._ANDROID.reset_population()
    core._ANDROID.state.generation = 1
    core._ANDROID.state.best_ever = -1e9
    core._ANDROID.state.last_best = 0.0
    _save_state()
    return "Training zurückgesetzt (Android Spezial)."


def get_visual_frame() -> str:
    return core.get_visual_frame()


def reset_visualization() -> str:
    return core.reset_visualization()


def get_template_frame() -> str:
    return core.get_template_frame()


def template_add_node(x: float, y: float) -> str:
    return core.template_add_node(x, y)


def template_add_bone(a: int, b: int) -> str:
    return core.template_add_bone(a, b)


def template_add_muscle(bi: int, bj: int) -> str:
    return core.template_add_muscle(bi, bj)


def template_add_muscle_by_nodes(a: int, b: int) -> str:
    return core.template_add_muscle_by_nodes(a, b)


def template_auto_muscles() -> str:
    return core.template_auto_muscles()


def template_clear() -> str:
    return core.template_clear()


def template_default() -> str:
    return core.template_default()


def template_save(name: str = "android_slot") -> str:
    return core.template_save(name)


def template_load(name: str = "android_slot") -> str:
    return core.template_load(name)


def template_list() -> str:
    return core.template_list()


_load_state()

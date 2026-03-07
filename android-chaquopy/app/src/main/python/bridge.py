import importlib.util
import pathlib
import traceback

_module_path = pathlib.Path(__file__).resolve().parent / "app_1.py"
_spec = importlib.util.spec_from_file_location("app_logic", _module_path)
app_logic = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(app_logic)


def hello():
    return "Python-Bridge aktiv"


def get_status():
    if hasattr(app_logic, "get_status"):
        try:
            return str(app_logic.get_status())
        except Exception as e:
            return f"get_status Fehler: {e}"
    return f"Modul geladen: {_module_path.name}"


def run_epoch():
    if hasattr(app_logic, "run_epoch"):
        try:
            return str(app_logic.run_epoch())
        except Exception:
            return "run_epoch Fehler:
" + traceback.format_exc()
    if hasattr(app_logic, "main"):
        try:
            result = app_logic.main()
            return f"main() ausgef?hrt: {result}"
        except Exception:
            return "main() Fehler:
" + traceback.format_exc()
    return "Keine run_epoch()/main() gefunden, aber Modul wurde geladen."

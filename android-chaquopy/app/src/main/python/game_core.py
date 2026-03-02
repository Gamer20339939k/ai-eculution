# Auto-generiert von apk_builder.py
import importlib.util
from pathlib import Path

_module_path = Path(__file__).with_name("app_logic.py")
_spec = importlib.util.spec_from_file_location("app_logic", _module_path)
app_logic = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(app_logic)


def hello():
    return "Python-Bridge aktiv"

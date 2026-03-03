from __future__ import annotations

import traceback
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

import app_logic


class EvoApp(toga.App):
    def startup(self) -> None:
        self.output = toga.MultilineTextInput(readonly=True, style=Pack(flex=1, padding=8))
        run_btn = toga.Button("Run Epoch", on_press=self.on_run, style=Pack(flex=1, padding=4))
        reset_btn = toga.Button("Reset", on_press=self.on_reset, style=Pack(flex=1, padding=4))

        btn_box = toga.Box(children=[run_btn, reset_btn], style=Pack(direction=ROW))
        root = toga.Box(children=[self.output, btn_box], style=Pack(direction=COLUMN, padding=8))
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = root
        self.main_window.show()
        self.output.value = self._safe_call("get_status")

    def _safe_call(self, name: str) -> str:
        try:
            fn = getattr(app_logic, name, None)
            if not callable(fn):
                return f"{name} nicht gefunden."
            return str(fn())
        except Exception:
            return traceback.format_exc()

    def on_run(self, widget) -> None:
        self.output.value = self._safe_call("run_epoch")

    def on_reset(self, widget) -> None:
        fn = getattr(app_logic, "reset_training", None)
        if callable(fn):
            self.output.value = str(fn())
        else:
            self.output.value = "reset_training nicht gefunden."


def main():
    return EvoApp()

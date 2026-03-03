from __future__ import annotations

import asyncio
import json
import traceback
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

import app_logic


class EvoApp(toga.App):
    def startup(self) -> None:
        self.auto_running = False
        self.output = toga.MultilineTextInput(readonly=True, style=Pack(flex=1, padding=6))
        self.visual = toga.MultilineTextInput(readonly=True, style=Pack(flex=1, padding=6))
        run_btn = toga.Button("Run Epoch", on_press=self.on_run, style=Pack(flex=1, padding=4))
        reset_btn = toga.Button("Reset", on_press=self.on_reset, style=Pack(flex=1, padding=4))
        step_btn = toga.Button("Visual Step", on_press=self.on_visual_step, style=Pack(flex=1, padding=4))
        self.auto_btn = toga.Button("Auto: AUS", on_press=self.on_toggle_auto, style=Pack(flex=1, padding=4))

        row1 = toga.Box(children=[run_btn, reset_btn], style=Pack(direction=ROW))
        row2 = toga.Box(children=[step_btn, self.auto_btn], style=Pack(direction=ROW))
        root = toga.Box(children=[self.output, self.visual, row1, row2], style=Pack(direction=COLUMN, padding=8))
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = root
        self.main_window.show()
        self.output.value = self._safe_call("get_status")
        self._update_visual()
        self.add_background_task(self._auto_loop)

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
        self._update_visual()

    def on_reset(self, widget) -> None:
        fn = getattr(app_logic, "reset_training", None)
        if callable(fn):
            self.output.value = str(fn())
        else:
            self.output.value = "reset_training nicht gefunden."
        rv = getattr(app_logic, "reset_visualization", None)
        if callable(rv):
            try:
                rv()
            except Exception:
                pass
        self._update_visual()

    def on_visual_step(self, widget) -> None:
        self._update_visual()

    def on_toggle_auto(self, widget) -> None:
        self.auto_running = not self.auto_running
        self.auto_btn.label = "Auto: AN" if self.auto_running else "Auto: AUS"

    async def _auto_loop(self, widget) -> None:
        while True:
            if self.auto_running:
                self._update_visual()
            await asyncio.sleep(0.12)

    def _update_visual(self) -> None:
        fn = getattr(app_logic, "get_visual_frame", None)
        if not callable(fn):
            self.visual.value = "Visualisierung: get_visual_frame fehlt."
            return
        try:
            raw = str(fn())
            frame = json.loads(raw)
        except Exception:
            self.visual.value = "Visualisierung Fehler:\n" + traceback.format_exc()
            return

        gen = frame.get("generation", "?")
        creatures = frame.get("creatures", []) or []
        lines = [f"Generation: {gen}", f"Kreaturen sichtbar: {len(creatures)}"]
        for i, c in enumerate(creatures[:8], 1):
            nodes = c.get("nodes", []) or []
            leader = " *LEADER*" if c.get("leader") else ""
            if nodes:
                cx = sum(float(n[0]) for n in nodes) / len(nodes)
                cy = sum(float(n[1]) for n in nodes) / len(nodes)
                lines.append(f"{i:02d}: x={cx:7.1f} y={cy:7.1f} nodes={len(nodes)}{leader}")
            else:
                lines.append(f"{i:02d}: keine Nodes{leader}")
        self.visual.value = "\n".join(lines)


def main():
    return EvoApp()

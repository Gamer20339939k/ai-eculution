from __future__ import annotations

import json
import math
import random
import re
try:
    import tkinter as tk
except Exception:  # tkinter not available on Android/Chaquopy
    tk = None
from dataclasses import dataclass
from pathlib import Path

# ============================================================
# Konstanten
# ============================================================
APP_TITLE = "Creature Evolution Lab (Single File)"
CANVAS_WIDTH = 1200
CANVAS_HEIGHT = 760
GROUND_HEIGHT = 120
GROUND_Y = CANVAS_HEIGHT - GROUND_HEIGHT
TIME_STEP = 1 / 60
METER_PX = 50

NODE_RADIUS = 8
NODE_MASS = 1.0
GRAVITY = 1450.0
AIR_DRAG = 0.997
GROUND_FRICTION = 0.90
BOUNCE_DAMP = 0.1
MAX_SPEED = 560.0

SPRING_K = 900.0
SPRING_D = 24.0
MUSCLE_SCALE = 0.75

GOAL_X = CANVAS_WIDTH - 120
GOAL_RADIUS = 28

POPULATION = 32
ELITE = 6
SURVIVOR_RATIO = 0.28
RANDOM_INJECTION = 1
GEN_TIME = 18.0
MUTATION_RATE = 0.13
MUTATION_STD = 0.20

SAVE_DIR = Path("saved_creatures")
TEMPLATE_FILE = SAVE_DIR / "creature_template.json"
BEST_FILE = SAVE_DIR / "best_genome.json"


# ============================================================
# Datenmodelle
# ============================================================
@dataclass
class NodeDef:
    x: float
    y: float


@dataclass
class EdgeDef:
    a: int
    b: int
    rest: float


@dataclass
class Template:
    name: str
    color: str
    nodes: list[NodeDef]
    bones: list[EdgeDef]
    muscles: list[EdgeDef]

    def validate(self) -> tuple[bool, str]:
        if len(self.nodes) < 2:
            return False, "mindestens 2 Knoten"
        if len(self.bones) + len(self.muscles) < 1:
            return False, "mindestens 1 Kante"
        seen: set[tuple[int, int, str]] = set()
        bone_keys: set[tuple[int, int]] = set()
        for e in self.bones:
            if e.a == e.b:
                return False, "Kante mit gleichem Start/Ziel"
            if min(e.a, e.b) < 0 or max(e.a, e.b) >= len(self.nodes):
                return False, "Kantenindex ausserhalb"
            key = (*sorted((e.a, e.b)), "bone")
            if key in seen:
                return False, "Doppelte Kante"
            seen.add(key)
            bone_keys.add(tuple(sorted((e.a, e.b))))
            if e.rest <= 0:
                return False, "Restlaenge <= 0"
        for e in self.muscles:
            if e.a == e.b:
                return False, "Muskel mit gleichem Start/Ziel"
            if min(e.a, e.b) < 0 or max(e.a, e.b) >= len(self.bones):
                return False, "Muskelindex ausserhalb"
            key = (*sorted((e.a, e.b)), "muscle")
            if key in seen:
                return False, "Doppelter Muskel"
            seen.add(key)
            if e.rest <= 0:
                return False, "Restlaenge <= 0"
        return True, "ok"

    def recompute_rests(self) -> None:
        for e in self.bones:
            n1, n2 = self.nodes[e.a], self.nodes[e.b]
            e.rest = max(6.0, math.hypot(n2.x - n1.x, n2.y - n1.y))
        for e in self.muscles:
            # Muscle indices refer to bones. Keep fallback for old node-based files.
            if 0 <= e.a < len(self.bones) and 0 <= e.b < len(self.bones):
                ba = self.bones[e.a]
                bb = self.bones[e.b]
                a1, a2 = self.nodes[ba.a], self.nodes[ba.b]
                b1, b2 = self.nodes[bb.a], self.nodes[bb.b]
                ma = ((a1.x + a2.x) * 0.5, (a1.y + a2.y) * 0.5)
                mb = ((b1.x + b2.x) * 0.5, (b1.y + b2.y) * 0.5)
                e.rest = max(6.0, math.hypot(mb[0] - ma[0], mb[1] - ma[1]))
            elif 0 <= e.a < len(self.nodes) and 0 <= e.b < len(self.nodes):
                n1, n2 = self.nodes[e.a], self.nodes[e.b]
                e.rest = max(6.0, math.hypot(n2.x - n1.x, n2.y - n1.y))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "color": self.color,
            "nodes": [{"x": n.x, "y": n.y} for n in self.nodes],
            "bones": [{"a": e.a, "b": e.b, "rest": e.rest} for e in self.bones],
            "muscles": [{"a": e.a, "b": e.b, "rest": e.rest} for e in self.muscles],
        }

    @staticmethod
    def from_dict(data: dict) -> "Template":
        bones = [EdgeDef(int(e["a"]), int(e["b"]), float(e["rest"])) for e in data.get("bones", [])]
        muscles = [EdgeDef(int(e["a"]), int(e["b"]), float(e["rest"])) for e in data.get("muscles", [])]
        if not bones and "edges" in data:
            bones = [EdgeDef(int(e["a"]), int(e["b"]), float(e["rest"])) for e in data.get("edges", [])]
        t = Template(
            name=str(data.get("name", "Kreatur")),
            color=str(data.get("color", "#7dd3fc")),
            nodes=[NodeDef(float(n["x"]), float(n["y"])) for n in data.get("nodes", [])],
            bones=bones,
            muscles=muscles,
        )
        ok, msg = t.validate()
        if not ok:
            raise ValueError(msg)
        return t

    @staticmethod
    def default() -> "Template":
        nodes = [
            NodeDef(170, 480),
            NodeDef(220, 440),
            NodeDef(280, 480),
            NodeDef(220, 520),
        ]
        edges = [
            EdgeDef(0, 1, 64),
            EdgeDef(1, 2, 64),
            EdgeDef(0, 2, 115),
            EdgeDef(0, 3, 64),
            EdgeDef(2, 3, 64),
            EdgeDef(1, 3, 80),
        ]
        return Template("Starter", "#7dd3fc", nodes, edges, [])

# ============================================================
# Genome + Evolution
# ============================================================
@dataclass
class Genome:
    phase: list[float]
    amp: list[float]
    bias: list[float]
    freq: list[float]

    @staticmethod
    def random(muscles: int) -> "Genome":
        return Genome(
            phase=[random.uniform(0, 2 * math.pi) for _ in range(muscles)],
            amp=[random.uniform(0.2, 1.1) for _ in range(muscles)],
            bias=[random.uniform(-0.25, 0.25) for _ in range(muscles)],
            freq=[random.uniform(0.7, 1.4) for _ in range(muscles)],
        )

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "amp": self.amp,
            "bias": self.bias,
            "freq": self.freq,
        }

    @staticmethod
    def from_dict(data: dict) -> "Genome":
        return Genome(
            phase=[float(x) for x in data.get("phase", [])],
            amp=[float(x) for x in data.get("amp", [])],
            bias=[float(x) for x in data.get("bias", [])],
            freq=[float(x) for x in data.get("freq", [])],
        )

    def valid_for(self, muscles: int) -> bool:
        return all(len(v) == muscles for v in (self.phase, self.amp, self.bias, self.freq))


def activate(g: Genome, i: int, t: float, energy: float) -> float:
    return (math.sin(t * 6.0 * g.freq[i] + g.phase[i]) * g.amp[i] + g.bias[i]) * energy


def crossover(a: Genome, b: Genome) -> Genome:
    pick = lambda x, y: x if random.random() < 0.5 else y
    return Genome(
        phase=[pick(x, y) for x, y in zip(a.phase, b.phase)],
        amp=[pick(x, y) for x, y in zip(a.amp, b.amp)],
        bias=[pick(x, y) for x, y in zip(a.bias, b.bias)],
        freq=[pick(x, y) for x, y in zip(a.freq, b.freq)],
    )


def mutate(g: Genome, rate: float, std: float) -> Genome:
    def m(v: float, lo: float, hi: float) -> float:
        if random.random() < rate:
            v += random.gauss(0, std)
        return max(lo, min(hi, v))

    return Genome(
        phase=[m(v, 0, 2 * math.pi) for v in g.phase],
        amp=[m(v, 0.0, 1.8) for v in g.amp],
        bias=[m(v, -0.6, 0.6) for v in g.bias],
        freq=[m(v, 0.4, 2.0) for v in g.freq],
    )


@dataclass
class EvoState:
    generation: int = 1
    elapsed: float = 0.0
    best_ever: float = -1e9
    last_best: float = 0.0
    render_speed: int = 1
    mut_rate: float = MUTATION_RATE
    mut_std: float = MUTATION_STD
    stagnation: int = 0
    survivors: int = 0
    culled: int = 0


# ============================================================
# Physik
# ============================================================
@dataclass
class NodeState:
    x: float
    y: float
    vx: float
    vy: float


class Creature:
    def __init__(self, template: Template, genome: Genome, color: str) -> None:
        self.template = template
        self.genome = genome
        self.color = color
        self.nodes: list[NodeState] = []
        self.score = 0.0
        self.alive = True
        self.max_x = 0.0
        self.start_x = 0.0
        self.energy = 0.0
        self.stuck = 0
        self.goal = False
        self.reset()

    def reset(self) -> None:
        self.nodes = [
            NodeState(
                n.x + random.uniform(-8, 8),
                n.y + random.uniform(-5, 5),
                random.uniform(-12, 12),
                0.0,
            )
            for n in self.template.nodes
        ]
        self.start_x = self.center_x
        self.max_x = self.start_x
        self.score = 0.0
        self.alive = True
        self.energy = 0.0
        self.stuck = 0
        self.goal = False

    @property
    def center_x(self) -> float:
        return sum(n.x for n in self.nodes) / len(self.nodes)

    @property
    def center_y(self) -> float:
        return sum(n.y for n in self.nodes) / len(self.nodes)

    def update(self, t: float, energy_factor: float) -> None:
        fx = [0.0] * len(self.nodes)
        fy = [0.0] * len(self.nodes)

        for i, n in enumerate(self.nodes):
            fy[i] += GRAVITY * NODE_MASS
            n.vx *= AIR_DRAG
            n.vy *= AIR_DRAG

        for e in self.template.bones:
            a = self.nodes[e.a]
            b = self.nodes[e.b]
            dx, dy = b.x - a.x, b.y - a.y
            dist = max(1e-6, math.hypot(dx, dy))
            nx, ny = dx / dist, dy / dist
            target = e.rest
            rvx, rvy = b.vx - a.vx, b.vy - a.vy
            rel = rvx * nx + rvy * ny
            force = max(-3200.0, min(3200.0, -SPRING_K * (dist - target) - SPRING_D * rel))
            sfx, sfy = force * nx, force * ny
            fx[e.a] -= sfx
            fy[e.a] -= sfy
            fx[e.b] += sfx
            fy[e.b] += sfy

        for ei, e in enumerate(self.template.muscles):
            if e.a < 0 or e.b < 0 or e.a >= len(self.template.bones) or e.b >= len(self.template.bones):
                continue
            b1 = self.template.bones[e.a]
            b2 = self.template.bones[e.b]
            a1, a2 = self.nodes[b1.a], self.nodes[b1.b]
            b1m = ((a1.x + a2.x) * 0.5, (a1.y + a2.y) * 0.5)
            b1v = ((a1.vx + a2.vx) * 0.5, (a1.vy + a2.vy) * 0.5)
            c1, c2 = self.nodes[b2.a], self.nodes[b2.b]
            b2m = ((c1.x + c2.x) * 0.5, (c1.y + c2.y) * 0.5)
            b2v = ((c1.vx + c2.vx) * 0.5, (c1.vy + c2.vy) * 0.5)
            dx, dy = b2m[0] - b1m[0], b2m[1] - b1m[1]
            dist = max(1e-6, math.hypot(dx, dy))
            nx, ny = dx / dist, dy / dist
            target = e.rest * (1.0 + MUSCLE_SCALE * activate(self.genome, ei, t, energy_factor))
            rvx, rvy = b2v[0] - b1v[0], b2v[1] - b1v[1]
            rel = rvx * nx + rvy * ny
            force = max(-3200.0, min(3200.0, -SPRING_K * (dist - target) - SPRING_D * rel))
            sfx, sfy = force * nx, force * ny
            fx[b1.a] -= sfx * 0.5
            fy[b1.a] -= sfy * 0.5
            fx[b1.b] -= sfx * 0.5
            fy[b1.b] -= sfy * 0.5
            fx[b2.a] += sfx * 0.5
            fy[b2.a] += sfy * 0.5
            fx[b2.b] += sfx * 0.5
            fy[b2.b] += sfy * 0.5
            self.energy += abs(force) * 0.000014

        prev_x = self.center_x
        for i, n in enumerate(self.nodes):
            n.vx += (fx[i] / NODE_MASS) * TIME_STEP
            n.vy += (fy[i] / NODE_MASS) * TIME_STEP
            speed = math.hypot(n.vx, n.vy)
            if speed > MAX_SPEED:
                n.vx = n.vx / speed * MAX_SPEED
                n.vy = n.vy / speed * MAX_SPEED

            n.x += n.vx * TIME_STEP
            n.y += n.vy * TIME_STEP

            if n.x < NODE_RADIUS:
                n.x = NODE_RADIUS
                n.vx *= -0.2
            if n.x > CANVAS_WIDTH - NODE_RADIUS:
                n.x = CANVAS_WIDTH - NODE_RADIUS
                n.vx *= -0.2
            if n.y > GROUND_Y - NODE_RADIUS:
                n.y = GROUND_Y - NODE_RADIUS
                n.vy *= -BOUNCE_DAMP
                n.vx *= GROUND_FRICTION

        cx = self.center_x
        self.max_x = max(self.max_x, cx)
        if cx - prev_x < 0.02:
            self.stuck += 1

        self.goal = abs(GOAL_X - cx) < GOAL_RADIUS
        progress = max(0.0, (self.max_x - self.start_x) / 110.0)
        survival = max(0.0, 1.0 - abs(self.center_y - (GROUND_Y - 70)) / 240.0)
        goal_bonus = 8.0 if self.goal else 0.0
        self.score = progress * 3.0 + survival * 1.7 + goal_bonus - self.energy - self.stuck * 0.0007

        # Keine vorzeitige Eliminierung: Kreaturen leben bis Epochenende.


# ============================================================
# App
# ============================================================
class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)

        self.template = Template.default()
        self.state = EvoState()
        self.best_history: list[float] = []
        self.mean_history: list[float] = []
        self.population_size = POPULATION
        self.gen_time = GEN_TIME
        self.population = self.seed_population(self.template, self.population_size)

        self.mode = "editor"
        self.running = True
        self.energy_factor = 1.0
        self.selected: int | None = None
        self.pending_edge: int | None = None
        self.delete_mode = False
        self.tool_mode = "gelenk"  # gelenk | knochen | muskel
        self.drag_edge_start: int | None = None
        self.drag_pos: tuple[float, float] | None = None

        self.canvas = tk.Canvas(root, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="#0f172a", highlightthickness=0)
        self.canvas.pack(side="left")

        panel = tk.Frame(root)
        panel.pack(side="right", fill="y", padx=8, pady=8)

        self.status = tk.StringVar(value="Bereit")
        tk.Label(panel, textvariable=self.status, justify="left", wraplength=320).pack(anchor="w", pady=5)

        self.name_var = tk.StringVar(value=self.template.name)
        self.color_var = tk.StringVar(value=self.template.color)
        tk.Label(panel, text="Name").pack(anchor="w")
        tk.Entry(panel, textvariable=self.name_var).pack(fill="x")
        tk.Label(panel, text="Farbe (#RRGGBB)").pack(anchor="w")
        tk.Entry(panel, textvariable=self.color_var).pack(fill="x")

        tk.Label(panel, text="Population").pack(anchor="w")
        self.population_var = tk.IntVar(value=self.population_size)
        tk.Spinbox(panel, from_=2, to=256, textvariable=self.population_var).pack(fill="x")

        tk.Label(panel, text="Runde (Sekunden)").pack(anchor="w")
        self.gen_time_var = tk.DoubleVar(value=self.gen_time)
        tk.Spinbox(panel, from_=3, to=120, increment=1, textvariable=self.gen_time_var).pack(fill="x")

        tk.Button(panel, text="Template speichern", command=self.save_template).pack(fill="x", pady=2)
        tk.Button(panel, text="Template laden", command=self.load_template).pack(fill="x", pady=2)
        tk.Label(panel, text="Gespeicherte Kreaturen").pack(anchor="w", pady=(6, 0))
        self.saved_list = tk.Listbox(panel, height=6)
        self.saved_list.pack(fill="x", pady=2)
        tk.Button(panel, text="Auswaehlte laden", command=self.load_selected_template).pack(fill="x", pady=2)
        tk.Button(panel, text="Auswaehlte loeschen", command=self.delete_selected_template).pack(fill="x", pady=2)
        tk.Button(panel, text="Loeschmodus (Entf)", command=self.toggle_delete_mode).pack(fill="x", pady=2)
        self.btn_joint = tk.Button(panel, text="Gelenkmodus", command=lambda: self.set_tool_mode("gelenk"))
        self.btn_joint.pack(fill="x", pady=2)
        self.btn_bone = tk.Button(panel, text="Knochenmodus", command=lambda: self.set_tool_mode("knochen"))
        self.btn_bone.pack(fill="x", pady=2)
        self.btn_muscle = tk.Button(panel, text="Muskelmodus (E)", command=lambda: self.set_tool_mode("muskel"))
        self.btn_muscle.pack(fill="x", pady=2)
        self._tool_btn_bg = self.btn_joint.cget("bg")
        self._tool_btn_fg = self.btn_joint.cget("fg")
        self._update_tool_buttons()
        tk.Button(panel, text="Alles entfernen", command=self.clear_all).pack(fill="x", pady=2)
        tk.Button(panel, text="Undo (Backspace)", command=self.undo).pack(fill="x", pady=2)
        tk.Button(panel, text="Start Simulation", command=self.start_sim).pack(fill="x", pady=2)
        tk.Button(panel, text="Pause/Fortsetzen", command=self.toggle).pack(fill="x", pady=2)
        tk.Button(panel, text="Nächste Generation", command=self.next_gen).pack(fill="x", pady=2)
        tk.Button(panel, text="Bestes Genome speichern", command=self.save_best).pack(fill="x", pady=2)
        tk.Button(panel, text="Bestes Genome laden", command=self.load_best_seed).pack(fill="x", pady=2)

        tk.Label(panel, text="Energie").pack(anchor="w")
        self.energy = tk.DoubleVar(value=1.0)
        tk.Scale(panel, from_=0.4, to=1.8, resolution=0.05, orient="horizontal", variable=self.energy, command=self._set_energy).pack(fill="x")

        self.show_best_only = tk.BooleanVar(value=False)
        tk.Checkbutton(panel, text="Nur beste anzeigen", variable=self.show_best_only).pack(anchor="w", pady=(6, 0))

        self.time_var = tk.StringVar(value="Zeit: 0.0 s")
        tk.Label(panel, textvariable=self.time_var, anchor="w").pack(fill="x")

        self.turbo = tk.BooleanVar(value=False)
        tk.Checkbutton(panel, text="Turbo (volle CPU)", variable=self.turbo).pack(anchor="w", pady=(6, 0))

        help_text = (
            "Editor: Gelenk/Knochen/Muskel per Modus-Button | E = Muskelmodus\n"
            "Muskel verbindet Knochen-Mitten | X Kante loeschen | Entf Loeschmodus\n"
            "Backspace Undo | Enter Start\n"
            "Simulation: Space Pause | N Next Gen | 1/2/3/4 Speed"
        )
        tk.Label(panel, text=help_text, justify="left", wraplength=320).pack(anchor="w", pady=8)

        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.root.bind("<e>", lambda _e: self.toggle_edge_mode())
        self.root.bind("<x>", lambda _e: self._delete_edge())
        self.root.bind("<BackSpace>", lambda _e: self.undo())
        self.root.bind("<Delete>", lambda _e: self.toggle_delete_mode())
        self.root.bind("<Shift-Delete>", lambda _e: self.clear_all())
        self.root.bind("<Return>", lambda _e: self.start_sim())
        self.root.bind("<space>", lambda _e: self.toggle())
        self.root.bind("<n>", lambda _e: self.next_gen())
        self.root.bind("1", lambda _e: self._speed(1))
        self.root.bind("2", lambda _e: self._speed(2))
        self.root.bind("3", lambda _e: self._speed(4))
        self.root.bind("4", lambda _e: self._speed(8))

        self.refresh_saved_list()
        self.loop()

    @staticmethod
    def rand_color() -> str:
        return f"#{random.randint(80,230):02x}{random.randint(80,230):02x}{random.randint(90,235):02x}"

    def seed_population(self, template: Template, size: int) -> list[Creature]:
        out: list[Creature] = []
        for i in range(size):
            g = Genome.random(len(template.muscles))
            color = template.color if i == 0 else self.rand_color()
            out.append(Creature(template, g, color))
        return out

    def _speed(self, value: int) -> None:
        self.state.render_speed = value

    def _set_energy(self, _v: str) -> None:
        self.energy_factor = float(self.energy.get())

    def _apply_meta(self) -> None:
        self.template.name = self.name_var.get().strip() or "Kreatur"
        self.template.color = self.color_var.get().strip() or "#7dd3fc"

    def _safe_filename(self, name: str) -> str:
        name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name.strip())
        return name or "kreatur"

    def refresh_saved_list(self) -> None:
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(SAVE_DIR.glob("*.json"))
        self.saved_list.delete(0, tk.END)
        for f in files:
            self.saved_list.insert(tk.END, f.name)

    def load_selected_template(self) -> None:
        if not self.saved_list.curselection():
            self.status.set("Kein Eintrag ausgewaehlt")
            return
        name = self.saved_list.get(self.saved_list.curselection()[0])
        try:
            t = Template.from_dict(json.loads((SAVE_DIR / name).read_text(encoding="utf-8")))
            self.template = t
            self.name_var.set(t.name)
            self.color_var.set(t.color)
            self.mode = "editor"
            self.status.set(f"Template geladen: {name}")
        except Exception as exc:  # noqa: BLE001
            self.status.set(f"Laden fehlgeschlagen: {exc}")

    def delete_selected_template(self) -> None:
        if not self.saved_list.curselection():
            self.status.set("Kein Eintrag ausgewaehlt")
            return
        name = self.saved_list.get(self.saved_list.curselection()[0])
        try:
            path = SAVE_DIR / name
            if path.exists():
                path.unlink()
            self.refresh_saved_list()
            self.status.set(f"Geloescht: {name}")
        except Exception as exc:  # noqa: BLE001
            self.status.set(f"Loeschen fehlgeschlagen: {exc}")

    def save_template(self) -> None:
        self._apply_meta()
        ok, msg = self.template.validate()
        if not ok:
            self.status.set(f"Fehler: {msg}")
            return
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        filename = self._safe_filename(self.template.name) + ".json"
        target = SAVE_DIR / filename
        target.write_text(json.dumps(self.template.to_dict(), indent=2), encoding="utf-8")
        self.refresh_saved_list()
        self.status.set(f"Gespeichert: {target}")

    def load_template(self) -> None:
        if self.saved_list.curselection():
            self.load_selected_template()
            return
        try:
            t = Template.from_dict(json.loads(TEMPLATE_FILE.read_text(encoding="utf-8")))
            self.template = t
            self.name_var.set(t.name)
            self.color_var.set(t.color)
            self.mode = "editor"
            self.status.set("Template geladen")
        except Exception as exc:  # noqa: BLE001
            self.status.set(f"Laden fehlgeschlagen: {exc}")

    def save_best(self) -> None:
        if not self.population:
            return
        best = max(self.population, key=lambda c: c.score)
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {"template": self.template.to_dict(), "genome": best.genome.to_dict(), "score": best.score}
        BEST_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.status.set(f"Bestes gespeichert: {BEST_FILE}")

    def load_best_seed(self) -> None:
        try:
            data = json.loads(BEST_FILE.read_text(encoding="utf-8"))
            t = Template.from_dict(data["template"])
            g = Genome.from_dict(data["genome"])
            if not g.valid_for(len(t.muscles)):
                raise ValueError("Genome passt nicht zum Template")
            self.template = t
            self.name_var.set(t.name)
            self.color_var.set(t.color)
            self.start_sim()
            self.population[0].genome = g
            self.population[0].color = t.color
            self.status.set("Bestes Genome geladen")
        except Exception as exc:  # noqa: BLE001
            self.status.set(f"Genome laden fehlgeschlagen: {exc}")

    def start_sim(self) -> None:
        self._apply_meta()
        self.template.recompute_rests()
        ok, msg = self.template.validate()
        if not ok:
            self.status.set(f"Start blockiert: {msg}")
            return
        try:
            self.population_size = max(2, int(self.population_var.get()))
        except Exception:  # noqa: BLE001
            self.population_size = POPULATION
        try:
            self.gen_time = max(3.0, float(self.gen_time_var.get()))
        except Exception:  # noqa: BLE001
            self.gen_time = GEN_TIME
        self.mode = "sim"
        self.running = True
        self.delete_mode = False
        self.tool_mode = "gelenk"
        self.drag_edge_start = None
        self.drag_pos = None
        self.state = EvoState()
        self._update_tool_buttons()
        self.best_history = []
        self.mean_history = []
        self.population = self.seed_population(self.template, self.population_size)
        self.state.survivors = self.population_size
        self.state.culled = 0
        self.status.set("Simulation gestartet")

    def toggle(self) -> None:
        if self.mode == "sim":
            self.running = not self.running

    def adapt_mutation(self) -> None:
        if len(self.best_history) < 6:
            return
        recent = self.best_history[-6:]
        if recent[-1] - recent[0] < 0.2:
            self.state.stagnation += 1
        else:
            self.state.stagnation = max(0, self.state.stagnation - 1)

        if self.state.stagnation > 2:
            self.state.mut_rate = min(0.35, self.state.mut_rate * 1.08)
            self.state.mut_std = min(0.55, self.state.mut_std * 1.10)
        else:
            vol = 0.0
            if len(recent) > 1:
                mean = sum(recent) / len(recent)
                var = sum((x - mean) ** 2 for x in recent) / len(recent)
                vol = var**0.5
            t = 0.15 if vol > 0.6 else 0.07
            self.state.mut_rate += (MUTATION_RATE - self.state.mut_rate) * t
            self.state.mut_std += (MUTATION_STD - self.state.mut_std) * t

    @staticmethod
    def tournament(ranked: list[Creature], k: int = 5) -> Creature:
        return max(random.sample(ranked, min(k, len(ranked))), key=lambda c: c.score)

    def evolve(self) -> None:
        ranked = sorted(self.population, key=lambda c: c.score, reverse=True)
        if not ranked:
            return

        scores = [c.score for c in ranked]
        self.state.last_best = scores[0]
        self.state.best_ever = max(self.state.best_ever, scores[0])
        self.best_history.append(scores[0])
        self.mean_history.append(sum(scores) / len(scores))
        self.adapt_mutation()

        if self.state.generation == 1:
            survivors_n = len(ranked)
        else:
            survivors_n = max(2, min(len(ranked), int(round(self.population_size * SURVIVOR_RATIO))))
        elites_n = min(ELITE, survivors_n)
        survivors = ranked[:survivors_n]
        elites = survivors[:elites_n]
        self.state.survivors = survivors_n
        self.state.culled = max(0, len(ranked) - survivors_n)

        new_pop: list[Creature] = [Creature(self.template, e.genome, e.color) for e in elites]
        for _ in range(min(RANDOM_INJECTION, max(0, self.population_size - len(new_pop)))):
            new_pop.append(Creature(self.template, Genome.random(len(self.template.muscles)), self.rand_color()))

        while len(new_pop) < self.population_size:
            p1 = self.tournament(survivors)
            p2 = self.tournament(survivors)
            parent_quality = max(p1.score, p2.score)
            elite_quality = max(1e-6, survivors[0].score)
            rank_factor = max(0.55, min(1.0, 1.0 - 0.35 * (parent_quality / elite_quality)))
            child = mutate(
                crossover(p1.genome, p2.genome),
                self.state.mut_rate * rank_factor,
                self.state.mut_std * rank_factor,
            )
            new_pop.append(Creature(self.template, child, self.rand_color()))

        self.population = new_pop[: self.population_size]
        self.state.generation += 1
        self.state.elapsed = 0.0

    def next_gen(self) -> None:
        if self.mode == "sim":
            self.evolve()

    def on_mouse_down(self, ev: tk.Event) -> None:
        if self.mode != "editor":
            return

        if self.delete_mode:
            i = self._pick_node(ev.x, ev.y)
            if i is not None:
                self.delete_node_at(i)
                return
            self.delete_mode = False
            self.status.set("Loeschmodus beendet")

        if self.tool_mode == "muskel":
            bi = self._pick_bone(ev.x, ev.y)
            if bi is None:
                return
            self.drag_edge_start = bi
            self.drag_pos = (ev.x, ev.y)
            self.status.set("Muskel: zu anderem Knochen ziehen")
            return

        if self.tool_mode == "knochen":
            i = self._pick_node(ev.x, ev.y)
            if i is None:
                return
            self.selected = i
            self.drag_edge_start = i
            self.drag_pos = (ev.x, ev.y)
            self.status.set("Knochen: zu zweitem Gelenk ziehen")
            return

        if self.tool_mode == "gelenk":
            i = self._pick_node(ev.x, ev.y)
            if i is None:
                self.template.nodes.append(NodeDef(float(ev.x), float(min(ev.y, GROUND_Y - NODE_RADIUS))))
                self.selected = len(self.template.nodes) - 1
                self.status.set(f"Gelenk {self.selected} erstellt")
                return
            self.selected = i
            self.status.set(f"Gelenk {i} gewählt")
            return

        i = self._pick_node(ev.x, ev.y)
        if i is None:
            self.template.nodes.append(NodeDef(float(ev.x), float(min(ev.y, GROUND_Y - NODE_RADIUS))))
            self.selected = len(self.template.nodes) - 1
            self.status.set(f"Gelenk {self.selected} erstellt")
            return

        prev = self.selected
        self.selected = i
        if prev is not None and prev != i:
            self.pending_edge = prev
        self.drag_edge_start = i
        n = self.template.nodes[i]
        self.drag_pos = (ev.x, ev.y)
        self.status.set(f"Gelenk {i} gewählt (ziehen für Knochen)")

    def on_mouse_drag(self, ev: tk.Event) -> None:
        if self.mode != "editor":
            return
        if self.drag_edge_start is None:
            return
        self.drag_pos = (ev.x, ev.y)

    def on_mouse_up(self, ev: tk.Event) -> None:
        if self.mode != "editor":
            return
        if self.drag_edge_start is None:
            return
        start = self.drag_edge_start
        self.drag_edge_start = None
        self.drag_pos = None
        if self.tool_mode == "muskel":
            bi = self._pick_bone(ev.x, ev.y)
            if bi is None or bi == start:
                return
            a, b = sorted((start, bi))
            if not self._muscle_exists(a, b):
                b1 = self.template.bones[a]
                b2 = self.template.bones[b]
                n1, n2 = self.template.nodes[b1.a], self.template.nodes[b1.b]
                m1 = ((n1.x + n2.x) * 0.5, (n1.y + n2.y) * 0.5)
                n3, n4 = self.template.nodes[b2.a], self.template.nodes[b2.b]
                m2 = ((n3.x + n4.x) * 0.5, (n3.y + n4.y) * 0.5)
                rest = max(6.0, math.hypot(m2[0] - m1[0], m2[1] - m1[1]))
                self.template.muscles.append(EdgeDef(a, b, rest))
                self.status.set(f"Muskel B{a}-B{b} erstellt")
            return
        i = self._pick_node(ev.x, ev.y)
        if i is None or i == start:
            return
        a, b = sorted((start, i))
        if self.tool_mode == "knochen" and not self._bone_exists(a, b):
            na, nb = self.template.nodes[a], self.template.nodes[b]
            self.template.bones.append(EdgeDef(a, b, math.hypot(nb.x - na.x, nb.y - na.y)))
            self.status.set(f"Knochen {a}-{b} erstellt")

    def _pick_node(self, x: float, y: float) -> int | None:
        for i, n in enumerate(self.template.nodes):
            if (n.x - x) ** 2 + (n.y - y) ** 2 <= (NODE_RADIUS * 2.6) ** 2:
                return i
        return None

    @staticmethod
    def _edge_key(a: int, b: int) -> tuple[int, int]:
        return tuple(sorted((a, b)))

    def _bone_exists(self, a: int, b: int) -> bool:
        key = self._edge_key(a, b)
        return any(self._edge_key(e.a, e.b) == key for e in self.template.bones)

    def _muscle_exists(self, a: int, b: int) -> bool:
        key = self._edge_key(a, b)
        return any(self._edge_key(e.a, e.b) == key for e in self.template.muscles)

    def _reindex_muscles(self, old_bones: list[EdgeDef], new_bones: list[EdgeDef]) -> None:
        old_keys = [self._edge_key(e.a, e.b) for e in old_bones]
        new_map: dict[tuple[int, int], int] = {self._edge_key(e.a, e.b): i for i, e in enumerate(new_bones)}
        new_muscles: list[EdgeDef] = []
        seen: set[tuple[int, int]] = set()
        for m in self.template.muscles:
            if m.a >= len(old_keys) or m.b >= len(old_keys):
                continue
            ka = old_keys[m.a]
            kb = old_keys[m.b]
            if ka not in new_map or kb not in new_map:
                continue
            a = new_map[ka]
            b = new_map[kb]
            if a == b:
                continue
            key = self._edge_key(a, b)
            if key in seen:
                continue
            seen.add(key)
            new_muscles.append(EdgeDef(a, b, m.rest))
        self.template.muscles = new_muscles

    def _pick_bone(self, x: float, y: float) -> int | None:
        def dist_point_to_seg(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
            dx, dy = x2 - x1, y2 - y1
            if dx == 0 and dy == 0:
                return math.hypot(px - x1, py - y1)
            t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
            t = max(0.0, min(1.0, t))
            cx, cy = x1 + t * dx, y1 + t * dy
            return math.hypot(px - cx, py - cy)

        best_i = None
        best_d = 1e9
        for i, e in enumerate(self.template.bones):
            n1, n2 = self.template.nodes[e.a], self.template.nodes[e.b]
            d = dist_point_to_seg(x, y, n1.x, n1.y, n2.x, n2.y)
            if d < best_d:
                best_d = d
                best_i = i
        if best_i is not None and best_d <= 10.0:
            return best_i
        return None

    def _arm_edge(self) -> None:
        if self.mode == "editor" and self.selected is not None:
            self.delete_mode = False
            self.pending_edge = self.selected
            self.status.set("E aktiv: zweiten Knoten anklicken")

    def _delete_edge(self) -> None:
        if self.mode != "editor" or self.pending_edge is None or self.selected is None:
            return
        a, b = sorted((self.pending_edge, self.selected))
        key = self._edge_key(a, b)
        old_bones = self.template.bones[:]
        self.template.bones = [e for e in self.template.bones if self._edge_key(e.a, e.b) != key]
        if len(self.template.bones) < len(old_bones):
            self._reindex_muscles(old_bones, self.template.bones)
            self.status.set(f"Knochen {a}-{b} geloescht")

    def toggle_delete_mode(self) -> None:
        if self.mode != "editor":
            return
        self.delete_mode = not self.delete_mode
        if self.delete_mode:
            self.pending_edge = None
            self.selected = None
            self.tool_mode = "gelenk"
            self.drag_edge_start = None
            self.drag_pos = None
            self.status.set("Loeschmodus aktiv: Knoten anklicken")
            self._update_tool_buttons()
        else:
            self.status.set("Loeschmodus beendet")

    def _update_tool_buttons(self) -> None:
        if not hasattr(self, "btn_joint"):
            return
        active_bg = "#2563eb"
        active_fg = "#ffffff"
        buttons = {
            "gelenk": self.btn_joint,
            "knochen": self.btn_bone,
            "muskel": self.btn_muscle,
        }
        for key, btn in buttons.items():
            if self.tool_mode == key:
                btn.configure(bg=active_bg, fg=active_fg)
            else:
                btn.configure(bg=self._tool_btn_bg, fg=self._tool_btn_fg)

    def set_tool_mode(self, mode: str) -> None:
        if self.mode != "editor":
            return
        if mode not in ("gelenk", "knochen", "muskel"):
            return
        self.tool_mode = mode
        self.delete_mode = False
        self.pending_edge = None
        self.drag_edge_start = None
        self.drag_pos = None
        if mode == "gelenk":
            self.status.set("Gelenkmodus aktiv: auf freie Flaeche klicken")
        elif mode == "knochen":
            self.status.set("Knochenmodus aktiv: von Gelenk zu Gelenk ziehen")
        else:
            self.status.set("Muskelmodus aktiv: von Knochen zu Knochen ziehen")
        self._update_tool_buttons()

    def toggle_edge_mode(self) -> None:
        if self.mode != "editor":
            return
        if self.tool_mode != "muskel":
            self.set_tool_mode("muskel")
        else:
            self.set_tool_mode("gelenk")

    def delete_node_at(self, idx: int) -> None:
        if self.mode != "editor":
            return
        if idx < 0 or idx >= len(self.template.nodes):
            return
        old_bones = self.template.bones[:]
        self.template.nodes.pop(idx)
        self.template.bones = [
            EdgeDef(
                a=e.a - (1 if e.a > idx else 0),
                b=e.b - (1 if e.b > idx else 0),
                rest=e.rest,
            )
            for e in self.template.bones
            if e.a != idx and e.b != idx
        ]
        self._reindex_muscles(old_bones, self.template.bones)
        self.selected = None
        self.pending_edge = None
        self.status.set(f"Knoten {idx} geloescht")

    def delete_node(self) -> None:
        if self.mode != "editor":
            return
        if self.selected is None:
            self.status.set("Kein Knoten ausgewaehlt")
            return
        self.delete_node_at(self.selected)

    def clear_all(self) -> None:
        if self.mode != "editor":
            return
        self.template.nodes = []
        self.template.bones = []
        self.template.muscles = []
        self.selected = None
        self.pending_edge = None
        self.delete_mode = False
        self.tool_mode = "gelenk"
        self.drag_edge_start = None
        self.drag_pos = None
        self.status.set("Alle Knoten/Kanten entfernt")
        self._update_tool_buttons()

    def undo(self) -> None:
        if self.mode != "editor":
            return
        if self.template.muscles:
            self.template.muscles.pop()
        elif self.template.bones:
            old_bones = self.template.bones[:]
            self.template.bones.pop()
            self._reindex_muscles(old_bones, self.template.bones)
        elif self.template.nodes:
            old_bones = self.template.bones[:]
            self.template.nodes.pop()
            m = len(self.template.nodes) - 1
            self.template.bones = [e for e in self.template.bones if e.a <= m and e.b <= m]
            self._reindex_muscles(old_bones, self.template.bones)

    def _simulate(self, steps: int) -> None:
        for _ in range(steps):
            for c in self.population:
                c.update(self.state.elapsed, self.energy_factor)
            self.state.elapsed += TIME_STEP
            if self.state.elapsed >= self.gen_time:
                self.evolve()
                break

    def draw(self) -> None:
        self.canvas.delete("all")
        bg = "#0f172a" if self.mode == "editor" else "#0b1220"
        self.canvas.create_rectangle(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT, fill=bg, outline="")
        self.canvas.create_rectangle(0, GROUND_Y, CANVAS_WIDTH, CANVAS_HEIGHT, fill="#6b4f2d", outline="")
        # Meter-Skala
        tick_h = 10
        for x in range(0, CANVAS_WIDTH + 1, METER_PX):
            self.canvas.create_line(x, GROUND_Y, x, GROUND_Y + tick_h, fill="#e2e8f0")
            if x % (METER_PX * 5) == 0:
                meters = x // METER_PX
                self.canvas.create_text(x + 2, GROUND_Y + tick_h + 2, anchor="nw", fill="#e2e8f0", text=f"{meters}m")
        self.canvas.create_oval(
            GOAL_X - GOAL_RADIUS,
            GROUND_Y - GOAL_RADIUS,
            GOAL_X + GOAL_RADIUS,
            GROUND_Y + GOAL_RADIUS,
            fill="#facc15",
            outline="#fff2b3",
            width=2,
        )

        if self.mode == "editor":
            for e in self.template.bones:
                n1, n2 = self.template.nodes[e.a], self.template.nodes[e.b]
                self.canvas.create_line(n1.x, n1.y, n2.x, n2.y, fill="#94a3b8", width=4)
            for e in self.template.muscles:
                if e.a < 0 or e.b < 0 or e.a >= len(self.template.bones) or e.b >= len(self.template.bones):
                    continue
                b1 = self.template.bones[e.a]
                b2 = self.template.bones[e.b]
                n1, n2 = self.template.nodes[b1.a], self.template.nodes[b1.b]
                n3, n4 = self.template.nodes[b2.a], self.template.nodes[b2.b]
                m1 = ((n1.x + n2.x) * 0.5, (n1.y + n2.y) * 0.5)
                m2 = ((n3.x + n4.x) * 0.5, (n3.y + n4.y) * 0.5)
                self.canvas.create_line(m1[0], m1[1], m2[0], m2[1], fill="#fb923c", width=4)
            if self.drag_edge_start is not None and self.drag_pos is not None:
                if self.tool_mode == "muskel":
                    if 0 <= self.drag_edge_start < len(self.template.bones):
                        b1 = self.template.bones[self.drag_edge_start]
                        n1, n2 = self.template.nodes[b1.a], self.template.nodes[b1.b]
                        m1 = ((n1.x + n2.x) * 0.5, (n1.y + n2.y) * 0.5)
                        self.canvas.create_line(m1[0], m1[1], self.drag_pos[0], self.drag_pos[1], fill="#fbbf24", width=3, dash=(4, 2))
                else:
                    n = self.template.nodes[self.drag_edge_start]
                    self.canvas.create_line(n.x, n.y, self.drag_pos[0], self.drag_pos[1], fill="#fbbf24", width=3, dash=(4, 2))
            for i, n in enumerate(self.template.nodes):
                o = "#ffffff" if i == self.selected else "#1e293b"
                f = "#f59e0b" if i == self.pending_edge else "#38bdf8"
                self.canvas.create_oval(n.x - NODE_RADIUS, n.y - NODE_RADIUS, n.x + NODE_RADIUS, n.y + NODE_RADIUS, fill=f, outline=o, width=2)
                self.canvas.create_text(n.x + 10, n.y - 10, text=str(i), fill="#e5e7eb", anchor="nw")
            ok, msg = self.template.validate()
            self.canvas.create_text(
                12,
                12,
                anchor="nw",
                fill="#e2e8f0",
                font=("Arial", 14, "bold"),
                text=(
                    f"Editor | Nodes={len(self.template.nodes)} Bones={len(self.template.bones)} "
                    f"Muscles={len(self.template.muscles)} | valid={ok} ({msg})"
                ),
            )
            return

        leader = max(self.population, key=lambda c: c.score) if self.population else None
        draw_pop = self.population
        if self.show_best_only.get() and leader is not None:
            draw_pop = [leader]
        for c in draw_pop:
            ec = "#fb7185" if c is leader else "#93c5fd"
            for e in c.template.bones:
                a, b = c.nodes[e.a], c.nodes[e.b]
                self.canvas.create_line(a.x, a.y, b.x, b.y, fill="#64748b", width=3)
            for e in c.template.muscles:
                if e.a < 0 or e.b < 0 or e.a >= len(c.template.bones) or e.b >= len(c.template.bones):
                    continue
                b1 = c.template.bones[e.a]
                b2 = c.template.bones[e.b]
                n1, n2 = c.nodes[b1.a], c.nodes[b1.b]
                n3, n4 = c.nodes[b2.a], c.nodes[b2.b]
                m1 = ((n1.x + n2.x) * 0.5, (n1.y + n2.y) * 0.5)
                m2 = ((n3.x + n4.x) * 0.5, (n3.y + n4.y) * 0.5)
                self.canvas.create_line(m1[0], m1[1], m2[0], m2[1], fill=ec, width=3)
            for n in c.nodes:
                self.canvas.create_oval(n.x - NODE_RADIUS, n.y - NODE_RADIUS, n.x + NODE_RADIUS, n.y + NODE_RADIUS, fill=c.color, outline="#fff" if c is leader else "", width=2)

        best = leader.score if leader else 0.0
        best_dist = 0.0
        if leader:
            best_dist = max(0.0, leader.max_x - leader.start_x)
        self.canvas.create_text(
            12,
            12,
            anchor="nw",
            fill="#e2e8f0",
            font=("Arial", 14, "bold"),
            text=(
                f"Epoche {self.state.generation} t={self.state.elapsed:.1f}/{self.gen_time:.0f}s | "
                f"best {best:.2f} | "
                f"best ever {self.state.best_ever:.2f} | dist {best_dist:.1f}px | "
                f"survive {self.state.survivors} cull {self.state.culled} | speed x{self.state.render_speed}"
            ),
        )
        self.canvas.create_text(
            12,
            36,
            anchor="nw",
            fill="#e2e8f0",
            font=("Arial", 12),
            text=f"Zeit: {self.state.elapsed:.1f} / {self.gen_time:.0f} s",
        )

    def loop(self) -> None:
        if self.mode == "sim" and self.running:
            try:
                self.gen_time = max(3.0, float(self.gen_time_var.get()))
            except Exception:  # noqa: BLE001
                self.gen_time = GEN_TIME
            steps = self.state.render_speed
            if self.turbo.get():
                steps = max(steps, 16)
            self._simulate(steps)
        self.draw()
        self.time_var.set(f"Zeit: {self.state.elapsed:.1f} / {self.gen_time:.0f} s")
        self.root.after(int(TIME_STEP * 1000), self.loop)


def main() -> None:
    if tk is None:
        raise RuntimeError('tkinter ist nicht verf?gbar (z.B. Android/Chaquopy).')
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()



# ============================================================
# Android/Chaquopy Bridge (headless simulation, no Tk UI)
# ============================================================
class _AndroidBridge:
    def __init__(self) -> None:
        self.template = Template.default()
        self.storage_dir = self._storage_dir()
        self.pop_size = POPULATION
        self.elite_count = ELITE
        self.survivor_ratio = SURVIVOR_RATIO
        self.random_injection = RANDOM_INJECTION
        self.gen_time = GEN_TIME
        self.mut_rate = MUTATION_RATE
        self.mut_std = MUTATION_STD
        self.selection_mode = "top"  # top | fitness
        self._ensure_muscles()
        self.state = EvoState()
        self.population: list[Creature] = []
        self.visual_time = 0.0
        self.reset_population()

    def _storage_dir(self) -> Path:
        try:
            from com.chaquo.python import Python  # type: ignore

            app = Python.getPlatform().getApplication()
            return Path(str(app.getFilesDir().getAbsolutePath())) / "saved_creatures"
        except Exception:
            return Path.cwd() / "saved_creatures"

    def _template_file(self, name: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("._-") or "template"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        return self.storage_dir / f"{safe}.json"

    def _ensure_muscles(self) -> None:
        if not self.template.muscles and len(self.template.bones) >= 3:
            self.template.muscles = [
                EdgeDef(0, 4, 90.0),
                EdgeDef(1, 3, 90.0),
                EdgeDef(2, 5, 90.0),
            ]
            self.template.recompute_rests()

    def reset_population(self) -> None:
        muscles = len(self.template.muscles)
        if muscles <= 0:
            self._ensure_muscles()
            muscles = len(self.template.muscles)
        self.population = [
            Creature(self.template, Genome.random(muscles), '#7dd3fc')
            for _ in range(max(4, int(self.pop_size)))
        ]
        self.state = EvoState()
        self.state.mut_rate = self.mut_rate
        self.state.mut_std = self.mut_std
        self.visual_time = 0.0

    def template_payload(self) -> dict:
        return {
            "w": CANVAS_WIDTH,
            "h": CANVAS_HEIGHT,
            "ground_y": GROUND_Y,
            "name": self.template.name,
            "nodes": [[n.x, n.y] for n in self.template.nodes],
            "bones": [[e.a, e.b] for e in self.template.bones],
            "muscles": [[e.a, e.b] for e in self.template.muscles],
        }

    def template_add_node(self, x: float, y: float) -> str:
        self.template.nodes.append(NodeDef(float(x), float(y)))
        self.reset_population()
        return f"Knoten hinzugefügt: {len(self.template.nodes)-1}"

    def template_add_bone(self, a: int, b: int) -> str:
        if a == b:
            return "Bone Fehler: gleicher Knoten"
        if min(a, b) < 0 or max(a, b) >= len(self.template.nodes):
            return "Bone Fehler: Index außerhalb"
        for e in self.template.bones:
            if {e.a, e.b} == {a, b}:
                return "Bone existiert bereits"
        n1, n2 = self.template.nodes[a], self.template.nodes[b]
        rest = max(6.0, math.hypot(n2.x - n1.x, n2.y - n1.y))
        self.template.bones.append(EdgeDef(a, b, rest))
        self.reset_population()
        return f"Bone hinzugefügt: {a}-{b}"

    def template_add_muscle(self, bi: int, bj: int) -> str:
        if bi == bj:
            return "Muscle Fehler: gleicher Bone"
        if min(bi, bj) < 0 or max(bi, bj) >= len(self.template.bones):
            return "Muscle Fehler: Bone-Index außerhalb"
        for e in self.template.muscles:
            if {e.a, e.b} == {bi, bj}:
                return "Muscle existiert bereits"
        self.template.muscles.append(EdgeDef(bi, bj, 20.0))
        self.template.recompute_rests()
        self.reset_population()
        return f"Muscle hinzugefügt: Bone {bi}-{bj}"

    def template_add_muscle_by_nodes(self, a: int, b: int) -> str:
        if min(a, b) < 0 or max(a, b) >= len(self.template.nodes):
            return "Muscle Fehler: Node-Index außerhalb"
        ai = -1
        bi = -1
        for i, e in enumerate(self.template.bones):
            if ai < 0 and (e.a == a or e.b == a):
                ai = i
            if bi < 0 and (e.a == b or e.b == b):
                bi = i
        if ai < 0 or bi < 0 or ai == bi:
            return "Muscle Fehler: passende Bones fehlen"
        return self.template_add_muscle(ai, bi)

    def template_auto_muscles(self) -> str:
        self.template.muscles = []
        if len(self.template.bones) >= 3:
            self.template.muscles.append(EdgeDef(0, min(1, len(self.template.bones)-1), 20.0))
            self.template.muscles.append(EdgeDef(0, min(2, len(self.template.bones)-1), 20.0))
            if len(self.template.bones) >= 4:
                self.template.muscles.append(EdgeDef(1, 3, 20.0))
        self.template.recompute_rests()
        self.reset_population()
        return f"Auto-Muscles: {len(self.template.muscles)}"

    def template_clear(self) -> str:
        self.template = Template("Neu", "#7dd3fc", [], [], [])
        self.reset_population()
        return "Template geleert"

    def template_default(self) -> str:
        self.template = Template.default()
        self._ensure_muscles()
        self.reset_population()
        return "Starter geladen"

    def template_save(self, name: str) -> str:
        if not self.template.nodes:
            return "Speichern Fehler: keine Knoten"
        payload = self.template.to_dict()
        payload["name"] = name or payload.get("name", "Template")
        fp = self._template_file(name or payload["name"])
        fp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return f"Gespeichert: {fp.name}"

    def template_list(self) -> list[str]:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        return [p.stem for p in sorted(self.storage_dir.glob("*.json"))]

    def template_load(self, name: str) -> str:
        fp = self._template_file(name)
        if not fp.exists():
            return f"Load Fehler: {name} fehlt"
        data = json.loads(fp.read_text(encoding="utf-8"))
        t = Template.from_dict(data)
        self.template = t
        self.reset_population()
        return f"Geladen: {name}"

    def reset_visualization(self) -> None:
        for c in self.population:
            c.reset()
        self.visual_time = 0.0

    def visual_frame(self, max_creatures: int = 10, sim_steps: int = 2) -> dict:
        sim_steps = max(1, min(8, int(sim_steps)))
        for _ in range(sim_steps):
            for c in self.population:
                if c.alive:
                    c.update(self.visual_time, 1.0)
            self.visual_time += TIME_STEP
            self.state.elapsed += TIME_STEP

        ranked = sorted(self.population, key=lambda c: c.score, reverse=True)
        show = ranked[: max(1, int(max_creatures))]
        leader = show[0] if show else None

        creatures: list[dict] = []
        bone_pairs = [[e.a, e.b] for e in self.template.bones]
        for c in show:
            creatures.append(
                {
                    "color": c.color,
                    "leader": c is leader,
                    "nodes": [[n.x, n.y] for n in c.nodes],
                    "bones": bone_pairs,
                }
            )
        return {
            "w": CANVAS_WIDTH,
            "h": CANVAS_HEIGHT,
            "ground_y": GROUND_Y,
            "generation": self.state.generation,
            "creatures": creatures,
        }

    def run_epoch(self) -> str:
        steps = max(1, int(self.gen_time / TIME_STEP))
        t = 0.0
        for _ in range(steps):
            for c in self.population:
                if c.alive:
                    c.update(t, 1.0)
            t += TIME_STEP

        self.population.sort(key=lambda c: c.score, reverse=True)
        best = self.population[0].score if self.population else 0.0
        self.state.last_best = best
        self.state.best_ever = max(self.state.best_ever, best)

        if self.state.generation <= 1:
            survivors = self.population[:]
        else:
            keep = max(2, int(len(self.population) * self.survivor_ratio))
            survivors = self.population[:keep]
        self.state.survivors = len(survivors)
        self.state.culled = len(self.population) - len(survivors)

        def pick_parent(pool: list[Creature]) -> Genome:
            if self.selection_mode != "fitness":
                return random.choice(pool).genome
            scores = [max(0.0, c.score) + 1e-6 for c in pool]
            total = sum(scores)
            if total <= 0:
                return random.choice(pool).genome
            r = random.random() * total
            acc = 0.0
            for c, w in zip(pool, scores):
                acc += w
                if acc >= r:
                    return c.genome
            return pool[-1].genome

        new_pop: list[Creature] = []
        for i in range(min(self.elite_count, len(survivors))):
            elite = survivors[i]
            clone = Creature(self.template, elite.genome, elite.color)
            new_pop.append(clone)

        muscles = len(self.template.muscles)
        parent_pool = self.population if self.selection_mode == "fitness" else survivors
        while len(new_pop) < self.pop_size - self.random_injection:
            a = pick_parent(parent_pool)
            b = pick_parent(parent_pool)
            child = mutate(crossover(a, b), self.state.mut_rate, self.state.mut_std)
            if not child.valid_for(muscles):
                child = Genome.random(muscles)
            new_pop.append(Creature(self.template, child, '#7dd3fc'))

        for _ in range(self.random_injection):
            new_pop.append(Creature(self.template, Genome.random(muscles), '#7dd3fc'))

        self.population = new_pop[: self.pop_size]
        self.state.generation += 1
        self.state.elapsed = 0.0

        return self.status()

    def status(self) -> str:
        return (
            f'Quelle: ai leanr walk.py\n'
            f'Generation: {self.state.generation}\n'
            f'Best: {self.state.last_best:.2f}\n'
            f'Best ever: {self.state.best_ever:.2f}\n'
            f'Survive/Cull: {self.state.survivors}/{self.state.culled}\n'
            f'Pop={self.pop_size} Zeit={self.gen_time:.0f}s Mut={self.mut_rate:.2f}/{self.mut_std:.2f} Sel={self.selection_mode}'
        )

    def adjust_config(self, key: str, delta: int) -> str:
        d = int(delta)
        if key == "population":
            self.pop_size = int(max(4, min(128, self.pop_size + d * 4)))
        elif key == "time":
            self.gen_time = float(max(4.0, min(60.0, self.gen_time + d * 2.0)))
        elif key == "mutation":
            self.mut_rate = float(max(0.01, min(0.7, self.mut_rate + d * 0.02)))
            self.mut_std = float(max(0.02, min(0.8, self.mut_std + d * 0.03)))
        elif key == "survivor":
            self.survivor_ratio = float(max(0.1, min(0.9, self.survivor_ratio + d * 0.05)))
        self.state.mut_rate = self.mut_rate
        self.state.mut_std = self.mut_std
        self.reset_population()
        return self.status()

    def toggle_selection_mode(self) -> str:
        self.selection_mode = "fitness" if self.selection_mode == "top" else "top"
        return f"Selection: {self.selection_mode}"


_ANDROID = _AndroidBridge()


def get_status() -> str:
    return _ANDROID.status()


def run_epoch() -> str:
    return _ANDROID.run_epoch()


def get_visual_frame() -> str:
    return json.dumps(_ANDROID.visual_frame(), ensure_ascii=False)


def reset_visualization() -> str:
    _ANDROID.reset_visualization()
    return "Visualisierung zurückgesetzt."



def get_template_frame() -> str:
    return json.dumps(_ANDROID.template_payload(), ensure_ascii=False)


def template_add_node(x: float, y: float) -> str:
    return _ANDROID.template_add_node(float(x), float(y))


def template_add_bone(a: int, b: int) -> str:
    return _ANDROID.template_add_bone(int(a), int(b))


def template_add_muscle(bi: int, bj: int) -> str:
    return _ANDROID.template_add_muscle(int(bi), int(bj))


def template_add_muscle_by_nodes(a: int, b: int) -> str:
    return _ANDROID.template_add_muscle_by_nodes(int(a), int(b))


def template_auto_muscles() -> str:
    return _ANDROID.template_auto_muscles()


def template_clear() -> str:
    return _ANDROID.template_clear()


def template_default() -> str:
    return _ANDROID.template_default()


def template_save(name: str = "android_slot") -> str:
    return _ANDROID.template_save(name)


def template_load(name: str = "android_slot") -> str:
    return _ANDROID.template_load(name)


def template_list() -> str:
    return json.dumps(_ANDROID.template_list(), ensure_ascii=False)


def adjust_config(key: str, delta: int) -> str:
    return _ANDROID.adjust_config(str(key), int(delta))


def toggle_selection_mode() -> str:
    return _ANDROID.toggle_selection_mode()

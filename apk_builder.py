import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path


CHAQUOPY_WORKFLOW_TEXT = """name: Build APK (Chaquopy)

on:
  workflow_dispatch:
  push:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Java 17
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: "17"

      - name: Setup Android SDK
        uses: android-actions/setup-android@v3

      - name: Setup Gradle
        uses: gradle/actions/setup-gradle@v4
        with:
          gradle-version: "8.10.2"

      - name: Build debug APK
        run: |
          cd android-chaquopy
          gradle assembleDebug --stacktrace

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: app-debug-apk
          path: android-chaquopy/app/build/outputs/apk/debug/*.apk
          if-no-files-found: error
"""


BEEWARE_WORKFLOW_TEXT = """name: Build APK (BeeWare)

on:
  workflow_dispatch:
  push:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Java 17
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: "17"

      - name: Setup Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Setup Android SDK
        uses: android-actions/setup-android@v3

      - name: Install Briefcase
        run: |
          python -m pip install --upgrade pip
          pip install briefcase

      - name: Build Android APK (BeeWare)
        run: |
          cd beeware-app
          briefcase create android --no-input
          briefcase build android --no-input
          briefcase package android --no-input

      - name: Collect APK
        run: |
          mkdir -p dist-apk
          find beeware-app -type f -name "*.apk" -exec cp {} dist-apk/ \\;
          ls -la dist-apk

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: app-debug-apk
          path: dist-apk/*.apk
          if-no-files-found: error
"""

CONFIG_FILE = "apk_builder_config.json"


def get_config_path(root: Path) -> Path:
    local = root / CONFIG_FILE
    if os.name == "nt":
        base = Path(os.getenv("APPDATA", str(Path.home())))
        return base / "apk_builder" / CONFIG_FILE
    return Path.home() / ".config" / "apk_builder" / CONFIG_FILE


def ensure(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_config(root: Path) -> dict:
    cfg = get_config_path(root)
    if not cfg.exists():
        legacy = root / CONFIG_FILE
        if legacy.exists():
            cfg = legacy
        else:
            return {}
    try:
        return json.loads(cfg.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(
    root: Path, repo: str | None, git_exe: str | None, token: str | None, engine: str | None
) -> None:
    cfg = get_config_path(root)
    ensure(cfg.parent)
    data = {"repo": repo or "", "git_exe": git_exe or "", "token": token or "", "engine": engine or ""}
    cfg.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run(cmd: list[str], cwd: Path) -> int:
    print(">", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(cwd)).returncode


def run_out(cmd: list[str], cwd: Path) -> str:
    return subprocess.check_output(cmd, cwd=str(cwd), text=True).strip()


def repo_rel(path: Path, root: Path) -> str | None:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:
        return None


def find_git(root: Path, git_exe: str | None) -> str | None:
    if git_exe:
        return git_exe
    found = shutil.which("git")
    if found:
        return found
    local = root / ".github" / "Git" / "cmd" / "git.exe"
    if local.exists():
        return str(local)
    return None


def parse_repo_from_origin(git: str, root: Path) -> str | None:
    try:
        url = run_out([git, "remote", "get-url", "origin"], root)
    except Exception:
        return None
    m = re.search(r"github\.com[:/]([^/]+/[^/.]+)(?:\.git)?$", url)
    return m.group(1) if m else None


def git_changed_paths(git: str, root: Path) -> list[str]:
    try:
        raw = run_out([git, "status", "--porcelain"], root)
    except Exception:
        return []
    out: list[str] = []
    for line in raw.splitlines():
        line = line.lstrip("\ufeff")
        if not line.strip():
            continue
        if len(line) >= 4 and line[2] == " ":
            entry = line[3:]
        else:
            parts = line.split(maxsplit=1)
            entry = parts[1] if len(parts) > 1 else ""
        if " -> " in entry:  # rename
            entry = entry.split(" -> ", 1)[1]
        out.append(entry.replace("\\", "/").strip())
    return out


def workflow_meta(engine: str) -> tuple[str, str, str]:
    eng = engine.lower().strip()
    if eng == "beeware":
        return ("build-apk-beeware.yml", "Build APK (BeeWare)", BEEWARE_WORKFLOW_TEXT)
    return ("build-apk-chaquopy.yml", "Build APK (Chaquopy)", CHAQUOPY_WORKFLOW_TEXT)


def ensure_beeware_scaffold(root: Path) -> list[Path]:
    app_root = root / "beeware-app"
    src_dir = app_root / "src" / "evocreatureai"
    ensure(src_dir)

    pyproject = app_root / "pyproject.toml"
    pyproject.write_text(
        """[build-system]
requires = ["briefcase"]
build-backend = "briefcase"

[tool.briefcase]
project_name = "Evo Creature AI"
bundle = "com.thilo"
version = "0.1.0"
url = "https://github.com/Gamer20339939k/ai-eculution"
license.file = "LICENSE"
author = "Thilo"
author_email = "thilo@example.com"

[tool.briefcase.app.evocreatureai]
formal_name = "Evo Creature AI"
description = "Learn-Walk Simulation (BeeWare)"
long_description = "Learn-Walk Simulation (BeeWare Android App)"
sources = ["src/evocreatureai"]
requires = ["toga>=0.4.8"]
""",
        encoding="utf-8",
    )

    readme = app_root / "README.md"
    if not readme.exists():
        readme.write_text("# BeeWare App\n", encoding="utf-8")

    license_file = app_root / "LICENSE"
    if not license_file.exists():
        license_file.write_text("MIT\n", encoding="utf-8")

    init_py = src_dir / "__init__.py"
    if not init_py.exists():
        init_py.write_text("", encoding="utf-8")

    app_py = src_dir / "app.py"
    app_py.write_text(
        """from __future__ import annotations

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
""",
        encoding="utf-8",
    )

    return [pyproject, readme, license_file, init_py, app_py]


def gh_api(method: str, url: str, token: str, data: dict | None = None) -> dict:
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    return json.loads(raw.decode("utf-8")) if raw else {}


def _to_epoch(ts: str | None) -> float:
    if not ts:
        return 0.0
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()
    except Exception:
        return 0.0


def wait_and_download_apk(
    repo: str,
    token: str,
    head_sha: str,
    out_dir: Path,
    engine: str = "chaquopy",
    branch: str | None = None,
    build_start_ts: float | None = None,
) -> tuple[Path, Path]:
    print("Warte auf GitHub-Build...")
    workflow_file, workflow_name, _ = workflow_meta(engine)

    run_id = None
    run_url = None
    for _ in range(30):
        runs = gh_api(
            "GET",
            f"https://api.github.com/repos/{repo}/actions/runs?head_sha={head_sha}&per_page=10",
            token,
        )
        for r in runs.get("workflow_runs", []):
            if r.get("name") == workflow_name:
                run_id = r.get("id")
                run_url = r.get("html_url")
                break
        if run_id:
            break
        time.sleep(5)

    if not run_id and branch:
        print("Kein Run per head_sha gefunden. Fallback: Branch-Runs prüfen...")
        dispatched = False
        try:
            gh_api(
                "POST",
                f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/dispatches",
                token,
                data={"ref": branch},
            )
            dispatched = True
            print("workflow_dispatch gestartet.")
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print("Hinweis: Kein Recht für workflow_dispatch (403). Suche nur vorhandene Runs.")
            else:
                raise

        for _ in range(30):
            runs = gh_api(
                "GET",
                f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/runs?branch={branch}&per_page=20",
                token,
            )
            for r in runs.get("workflow_runs", []):
                if r.get("name") != workflow_name:
                    continue
                if build_start_ts and _to_epoch(r.get("created_at")) + 120 < build_start_ts:
                    continue
                run_id = r.get("id")
                run_url = r.get("html_url")
                break
            if run_id:
                break
            time.sleep(5)

    # Zusätzlicher Fallback: allgemeine Push-Runs auf Branch suchen
    if not run_id and branch:
        print("Fallback 2: Suche neueste Push-Runs auf Branch...")
        for _ in range(24):
            runs = gh_api(
                "GET",
                f"https://api.github.com/repos/{repo}/actions/runs?branch={branch}&event=push&per_page=30",
                token,
            )
            for r in runs.get("workflow_runs", []):
                if r.get("name") != workflow_name:
                    continue
                if build_start_ts and _to_epoch(r.get("created_at")) + 180 < build_start_ts:
                    continue
                run_id = r.get("id")
                run_url = r.get("html_url")
                break
            if run_id:
                break
            time.sleep(5)

    if not run_id:
        raise SystemExit(
            "Fehler: Kein passender Workflow-Run gefunden. "
            "Prüfe in GitHub Actions, ob Workflow-Datei/Token/Repo stimmen. "
            f"Repo={repo}, Branch={branch or '-'}, SHA={head_sha[:8]}. "
            "Für workflow_dispatch braucht der Token Actions: Write."
        )

    while True:
        run_info = gh_api(
            "GET",
            f"https://api.github.com/repos/{repo}/actions/runs/{run_id}",
            token,
        )
        status = run_info.get("status")
        conclusion = run_info.get("conclusion")
        print(f"- Status: {status} ({conclusion})")
        if status == "completed":
            if conclusion != "success":
                raise SystemExit(
                    f"Fehler: Build fehlgeschlagen. Logs: {run_url or f'https://github.com/{repo}/actions/runs/{run_id}'}"
                )
            break
        time.sleep(10)

    artifacts = gh_api(
        "GET",
        f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts",
        token,
    )

    artifact = None
    for a in artifacts.get("artifacts", []):
        if a.get("name") == "app-debug-apk":
            artifact = a
            break

    if not artifact:
        raise SystemExit("Fehler: Artifact app-debug-apk nicht gefunden.")

    ensure(out_dir)
    zip_path = out_dir / "app-debug-apk.zip"

    # Wichtig: Redirect-Ziel ohne Authorization laden (sonst 401 bei Blob/S3 möglich)
    req = urllib.request.Request(
        artifact["archive_download_url"],
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
            return None

    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=120) as r:
            zip_bytes = r.read()
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            location = e.headers.get("Location")
            if not location:
                raise SystemExit("Fehler: Artifact-Redirect ohne Ziel-URL.")
            with urllib.request.urlopen(location, timeout=120) as r2:
                zip_bytes = r2.read()
        elif e.code in (401, 403):
            raise SystemExit(
                "Fehler: Artifact-Download nicht erlaubt (401/403). "
                "Token braucht für das Repo mindestens Actions: Read."
            ) from e
        else:
            raise

    zip_path.write_bytes(zip_bytes)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(out_dir)

    apk_files = sorted(out_dir.rglob("*.apk"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not apk_files:
        raise SystemExit(f"Fehler: Download okay, aber keine .apk gefunden in: {out_dir}")

    apk_path = apk_files[0].resolve()
    return zip_path.resolve(), apk_path


def pick_python_file(root: Path, force_menu: bool = False) -> Path:
    files: list[Path] = []

    # 1) Windows-Version (Projektwurzel)
    for p in sorted(root.glob("*.py"), key=lambda x: x.name.lower()):
        if p.name == "apk_builder.py":
            continue
        files.append(p)

    # 2) Android-Version (feste Spezial-Datei)
    android_main = root / "android-chaquopy" / "app" / "src" / "main" / "python" / "ai_lern_walk_android.py"
    if android_main.exists():
        files.append(android_main)

    # Duplikate entfernen, Reihenfolge behalten
    uniq: list[Path] = []
    seen: set[str] = set()
    for p in files:
        k = str(p.resolve()).lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(p)
    files = uniq
    if not files:
        raise SystemExit("Fehler: Keine .py-Datei im Projektordner gefunden.")
    if len(files) == 1 and not force_menu:
        return files[0]

    print("Wähle die Python-Datei für die APK:")
    for i, p in enumerate(files, 1):
        print(f"{i}) {p.relative_to(root)}")

    while True:
        c = input(f"Nummer eingeben (1-{len(files)}): ").strip()
        if c.isdigit() and 1 <= int(c) <= len(files):
            return files[int(c) - 1]
        print("Ungültig. Bitte nochmal.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automatische APK-Erstellung via Chaquopy/BeeWare + GitHub Actions"
    )
    parser.add_argument("source_py", nargs="?", help="Pfad zur .py-Datei")
    parser.add_argument("--engine", default=None, choices=["chaquopy", "beeware"], help="Build-Engine")
    parser.add_argument("--project-root", default=".", help="Projektwurzel")
    parser.add_argument("--target-name", default="app_logic.py", help="Zieldatei im Android-Python-Ordner")
    parser.add_argument("--auto-git", action="store_true", help="git add/commit/push automatisch")
    parser.add_argument("--full-auto", action="store_true", help="Zusätzlich auf Build warten und APK laden")
    parser.add_argument("--git-exe", default=None, help="Optionaler Pfad zu git.exe")
    parser.add_argument("--commit-msg", default="Prepare APK build", help="Commit-Nachricht")
    parser.add_argument("--repo", default=None, help="GitHub Repo: owner/name")
    parser.add_argument("--token", default=None, help="GitHub Token (oder GH_TOKEN/GITHUB_TOKEN)")
    parser.add_argument("--set-token", action="store_true", help="Gespeicherten Token jetzt neu eingeben")
    parser.add_argument("--out-dir", default="bin", help="Zielordner für APK")
    parser.add_argument("--choose", action="store_true", help="Datei-Auswahl immer anzeigen")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    cfg = load_config(root)

    # Repo/Git aus gespeicherter Konfiguration übernehmen
    if not args.repo and cfg.get("repo"):
        args.repo = cfg.get("repo")
    if not args.git_exe and cfg.get("git_exe"):
        args.git_exe = cfg.get("git_exe")
    if not args.token and cfg.get("token"):
        args.token = cfg.get("token")
    if not getattr(args, "engine", None) and cfg.get("engine"):
        args.engine = str(cfg.get("engine")).lower().strip() or args.engine

    if args.set_token:
        new_token = input("Neuen GitHub Token eingeben (leer = behalten): ").strip()
        if new_token:
            args.token = new_token

    # Komfort-Modus: Start ohne Parameter (z. B. aus IDLE)
    if len(sys.argv) == 1:
        print("IDLE-Modus aktiv: Auswahl + Full-Auto")
        args.choose = True
        args.full_auto = True
        args.auto_git = True
        eng = input("Engine wählen (1=Chaquopy, 2=BeeWare) [1]: ").strip()
        args.engine = "beeware" if eng == "2" else "chaquopy"
        if not args.repo:
            args.repo = input("GitHub Repo (owner/name): ").strip()
        if not args.token:
            args.token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
        if not args.token:
            args.token = input("GitHub Token: ").strip()
        else:
            change = input("Token wechseln? (j/N): ").strip().lower()
            if change in {"j", "ja", "y", "yes"}:
                new_token = input("Neuen GitHub Token: ").strip()
                if new_token:
                    args.token = new_token
        if not args.git_exe:
            local_git = root / ".github" / "Git" / "cmd" / "git.exe"
            if local_git.exists():
                args.git_exe = str(local_git)

    if not args.engine:
        default_engine = "chaquopy"
        if cfg.get("engine") in {"chaquopy", "beeware"}:
            default_engine = str(cfg.get("engine"))
        prompt = f"Engine wählen (1=Chaquopy, 2=BeeWare) [{1 if default_engine == 'chaquopy' else 2}]: "
        eng = input(prompt).strip()
        if eng == "1":
            args.engine = "chaquopy"
        elif eng == "2":
            args.engine = "beeware"
        else:
            args.engine = default_engine

    # Einmalige Angaben speichern (inkl. Token, in AppData/.config außerhalb des Projekts)
    save_config(root, args.repo, args.git_exe, args.token, args.engine)

    if args.source_py:
        src = Path(args.source_py)
        if not src.is_absolute():
            src = (root / src).resolve()
        else:
            src = src.resolve()
    else:
        src = pick_python_file(root, force_menu=args.choose)

    if not src.exists() or src.suffix.lower() != ".py":
        raise SystemExit("Fehler: source_py muss eine vorhandene .py-Datei sein.")

    generated_paths: list[Path] = []
    engine = args.engine.lower().strip()
    workflow_file, _workflow_name, workflow_text = workflow_meta(engine)

    if engine == "chaquopy":
        py_dir = root / "android-chaquopy" / "app" / "src" / "main" / "python"
        if not py_dir.exists():
            raise SystemExit("Fehler: android-chaquopy Struktur fehlt.")

        ensure(py_dir)
        target = py_dir / args.target_name
        shutil.copy2(src, target)
        generated_paths.append(target)

        wrapper = py_dir / "game_core.py"
        wrapper.write_text(
            f'''# Auto-generiert von apk_builder.py
import importlib.util
import traceback
from pathlib import Path

_module_path = Path(__file__).with_name("{args.target_name}")
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
            return f"get_status Fehler: {{e}}"
    return f"Modul geladen: {{_module_path.name}}"


def run_epoch():
    if hasattr(app_logic, "run_epoch"):
        try:
            return str(app_logic.run_epoch())
        except Exception:
            return "run_epoch Fehler:\\n" + traceback.format_exc()
    if hasattr(app_logic, "main"):
        try:
            result = app_logic.main()
            return f"main() ausgeführt: {{result}}"
        except Exception:
            return "main() Fehler:\\n" + traceback.format_exc()
    return "Keine run_epoch()/main() gefunden, aber Modul wurde geladen."
''',
            encoding="utf-8",
        )
        generated_paths.append(wrapper)
    else:
        scaffold = ensure_beeware_scaffold(root)
        generated_paths.extend(scaffold)
        target = root / "beeware-app" / "src" / "evocreatureai" / "app_logic.py"
        ensure(target.parent)
        shutil.copy2(src, target)
        generated_paths.append(target)

    workflow_path = root / ".github" / "workflows" / workflow_file
    ensure(workflow_path.parent)
    workflow_path.write_text(workflow_text, encoding="utf-8")
    generated_paths.append(workflow_path)
    for other in ["build-apk-chaquopy.yml", "build-apk-beeware.yml"]:
        if other == workflow_file:
            continue
        other_path = root / ".github" / "workflows" / other
        if other_path.exists():
            other_path.unlink()
            generated_paths.append(other_path)

    print("Fertig:")
    print(f"- Python kopiert nach: {target}")
    if engine == "chaquopy":
        print(f"- Wrapper erstellt:   {wrapper}")
    else:
        print(f"- BeeWare-Projekt:    {root / 'beeware-app'}")
    print(f"- Workflow erstellt:  {workflow_path}")

    do_auto_git = args.auto_git or args.full_auto
    if not do_auto_git:
        print("\nNächster Schritt: git add/commit/push")
        return

    git = find_git(root, args.git_exe)
    if not git:
        raise SystemExit("Fehler: git wurde nicht gefunden.")

    stage_paths: list[str] = []
    for p in generated_paths:
        rel = repo_rel(p, root)
        if rel:
            stage_paths.append(rel)
    src_rel = repo_rel(src, root)
    if src_rel:
        stage_paths.append(src_rel)

    changed = git_changed_paths(git, root)
    for rel in changed:
        if not rel:
            continue
        low = rel.lower()
        if "__pycache__" in low or low.endswith(".pyc"):
            continue
        if low.endswith((".apk", ".aab", ".zip", ".log", ".tmp", ".keystore", ".jks")):
            continue
        if rel == "apk_builder.py":
            stage_paths.append(rel)
            continue
        if rel.startswith(".github/workflows/"):
            stage_paths.append(rel)
            continue
        if rel.startswith("android-chaquopy/"):
            stage_paths.append(rel)
            continue
        if rel.startswith("beeware-app/"):
            stage_paths.append(rel)

    # Duplikate entfernen, Reihenfolge behalten
    stage_paths = list(dict.fromkeys(stage_paths))
    if not stage_paths:
        raise SystemExit("Fehler: Keine gültigen Repo-Dateien zum Stagen gefunden.")

    if run([git, "add", "--", *stage_paths], root) != 0:
        raise SystemExit("Fehler: git add fehlgeschlagen.")

    commit_rc = run([git, "commit", "-m", args.commit_msg, "--", *stage_paths], root)
    if commit_rc != 0:
        print("Hinweis: Kein neuer Commit in den Build-Dateien (evtl. keine Änderungen).")

    if run([git, "push"], root) != 0:
        raise SystemExit("Fehler: git push fehlgeschlagen.")

    print("Auto-Git fertig. Build läuft auf GitHub.")

    if not args.full_auto:
        return

    repo = args.repo or parse_repo_from_origin(git, root)
    token = args.token or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not repo:
        raise SystemExit("Fehler: Repo nicht erkannt. Nutze --repo owner/name")
    if not token:
        raise SystemExit("Fehler: Kein Token. Nutze --token oder GH_TOKEN setzen.")

    head_sha = run_out([git, "rev-parse", "HEAD"], root)
    branch = run_out([git, "rev-parse", "--abbrev-ref", "HEAD"], root)
    build_start_ts = time.time()
    zip_path, apk_path = wait_and_download_apk(
        repo,
        token,
        head_sha,
        root / args.out_dir,
        engine=engine,
        branch=branch if branch != "HEAD" else None,
        build_start_ts=build_start_ts,
    )
    print("")
    print("===== ERFOLG =====")
    print("APK-Erstellung erfolgreich.")
    print(f"ZIP gespeichert unter: {zip_path}")
    print(f"APK gespeichert unter: {apk_path}")
    print("==================")


if __name__ == "__main__":
    main()

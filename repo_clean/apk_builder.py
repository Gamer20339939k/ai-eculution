import argparse
import subprocess
import shutil
from pathlib import Path


WORKFLOW_TEXT = """name: Build APK (Chaquopy)

on:
  workflow_dispatch:
  push:
    paths:
      - "android-chaquopy/**"
      - ".github/workflows/build-apk-chaquopy.yml"

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


def ensure(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def run(cmd, cwd: Path) -> int:
    print(">", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(cwd)).returncode


def find_git(root: Path, git_exe: str | None) -> str | None:
    if git_exe:
        return git_exe
    g = shutil.which("git")
    if g:
        return g
    local = root / ".github" / "Git" / "cmd" / "git.exe"
    if local.exists():
        return str(local)
    return None


def pick_python_file(root: Path) -> Path:
    files = sorted(
        [
            p
            for p in root.glob("*.py")
            if p.name not in {"apk_builder.py"}
        ],
        key=lambda x: x.name.lower(),
    )
    if not files:
        raise SystemExit("Fehler: Keine .py-Datei im Projektordner gefunden.")
    if len(files) == 1:
        return files[0]

    print("Wähle die Python-Datei für die APK:")
    for i, p in enumerate(files, 1):
        print(f"{i}) {p.name}")

    while True:
        choice = input(f"Nummer eingeben (1-{len(files)}): ").strip()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(files):
                return files[idx - 1]
        print("Ungültig. Bitte nochmal.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bereitet ein .py-Programm für APK-Build via Chaquopy + GitHub Actions vor."
    )
    parser.add_argument("source_py", nargs="?", help="Pfad zur .py-Datei")
    parser.add_argument(
        "--project-root",
        default=".",
        help="Projektwurzel mit android-chaquopy Ordner (Standard: aktueller Ordner)",
    )
    parser.add_argument(
        "--target-name",
        default="app_logic.py",
        help="Dateiname im Android-Python-Ordner (Standard: app_logic.py)",
    )
    parser.add_argument(
        "--auto-git",
        action="store_true",
        help="Führt git add/commit/push automatisch aus",
    )
    parser.add_argument(
        "--git-exe",
        default=None,
        help="Optionaler Pfad zu git.exe",
    )
    parser.add_argument(
        "--commit-msg",
        default="Prepare APK build",
        help="Commit-Nachricht für --auto-git",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    if args.source_py:
        src = Path(args.source_py).resolve()
    else:
        src = pick_python_file(root)

    if not src.exists() or src.suffix.lower() != ".py":
        raise SystemExit("Fehler: source_py muss eine vorhandene .py-Datei sein.")

    py_dir = root / "android-chaquopy" / "app" / "src" / "main" / "python"
    if not py_dir.exists():
        raise SystemExit(
            "Fehler: android-chaquopy Struktur fehlt. Lege zuerst das Android-Chaquopy-Projekt an."
        )

    ensure(py_dir)
    target = py_dir / args.target_name
    shutil.copy2(src, target)

    wrapper = py_dir / "game_core.py"
    wrapper.write_text(
        f"""# Auto-generiert von apk_builder.py
import importlib.util
from pathlib import Path

_module_path = Path(__file__).with_name("{args.target_name}")
_spec = importlib.util.spec_from_file_location("app_logic", _module_path)
app_logic = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(app_logic)


def hello():
    return "Python-Bridge aktiv"
""",
        encoding="utf-8",
    )

    workflow_path = root / ".github" / "workflows" / "build-apk-chaquopy.yml"
    ensure(workflow_path.parent)
    workflow_path.write_text(WORKFLOW_TEXT, encoding="utf-8")

    print("Fertig:")
    print(f"- Python kopiert nach: {target}")
    print(f"- Wrapper erstellt:   {wrapper}")
    print(f"- Workflow erstellt:  {workflow_path}")
    print("")
    print("Nächster Schritt:")
    print("1) git add . && git commit -m \"Prepare APK build\" && git push")
    print("2) Auf GitHub -> Actions -> 'Build APK (Chaquopy)' starten")

    if args.auto_git:
        git = find_git(root, args.git_exe)
        if not git:
            raise SystemExit("Fehler: git wurde nicht gefunden.")
        if run([git, "add", "."], root) != 0:
            raise SystemExit("Fehler: git add fehlgeschlagen.")
        commit_rc = run([git, "commit", "-m", args.commit_msg], root)
        if commit_rc != 0:
            print("Hinweis: Kein neuer Commit (evtl. keine Änderungen).")
        push_rc = run([git, "push"], root)
        if push_rc != 0:
            raise SystemExit("Fehler: git push fehlgeschlagen.")
        print("Auto-Git fertig. GitHub Action sollte jetzt automatisch starten.")


if __name__ == "__main__":
    main()

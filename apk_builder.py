import argparse
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
import zipfile
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


def ensure(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def run(cmd: list[str], cwd: Path) -> int:
    print(">", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(cwd)).returncode


def run_out(cmd: list[str], cwd: Path) -> str:
    return subprocess.check_output(cmd, cwd=str(cwd), text=True).strip()


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


def wait_and_download_apk(repo: str, token: str, head_sha: str, out_dir: Path) -> None:
    print("Warte auf GitHub-Build...")

    run_id = None
    for _ in range(30):
        runs = gh_api(
            "GET",
            f"https://api.github.com/repos/{repo}/actions/runs?head_sha={head_sha}&per_page=10",
            token,
        )
        for r in runs.get("workflow_runs", []):
            if r.get("name") == "Build APK (Chaquopy)":
                run_id = r.get("id")
                break
        if run_id:
            break
        time.sleep(5)

    if not run_id:
        raise SystemExit("Fehler: Kein passender Workflow-Run gefunden.")

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
                    f"Fehler: Build fehlgeschlagen. Logs: https://github.com/{repo}/actions/runs/{run_id}"
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

    req = urllib.request.Request(
        artifact["archive_download_url"],
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        zip_path.write_bytes(r.read())

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(out_dir)

    print(f"APK geladen nach: {out_dir}")


def pick_python_file(root: Path, force_menu: bool = False) -> Path:
    files = sorted(
        [p for p in root.glob("*.py") if p.name not in {"apk_builder.py"}],
        key=lambda x: x.name.lower(),
    )
    if not files:
        raise SystemExit("Fehler: Keine .py-Datei im Projektordner gefunden.")
    if len(files) == 1 and not force_menu:
        return files[0]

    print("Wähle die Python-Datei für die APK:")
    for i, p in enumerate(files, 1):
        print(f"{i}) {p.name}")

    while True:
        c = input(f"Nummer eingeben (1-{len(files)}): ").strip()
        if c.isdigit() and 1 <= int(c) <= len(files):
            return files[int(c) - 1]
        print("Ungültig. Bitte nochmal.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automatische APK-Erstellung via Chaquopy + GitHub Actions"
    )
    parser.add_argument("source_py", nargs="?", help="Pfad zur .py-Datei")
    parser.add_argument("--project-root", default=".", help="Projektwurzel")
    parser.add_argument("--target-name", default="app_logic.py", help="Zieldatei im Android-Python-Ordner")
    parser.add_argument("--auto-git", action="store_true", help="git add/commit/push automatisch")
    parser.add_argument("--full-auto", action="store_true", help="Zusätzlich auf Build warten und APK laden")
    parser.add_argument("--git-exe", default=None, help="Optionaler Pfad zu git.exe")
    parser.add_argument("--commit-msg", default="Prepare APK build", help="Commit-Nachricht")
    parser.add_argument("--repo", default=None, help="GitHub Repo: owner/name")
    parser.add_argument("--token", default=None, help="GitHub Token (oder GH_TOKEN/GITHUB_TOKEN)")
    parser.add_argument("--out-dir", default="bin", help="Zielordner für APK")
    parser.add_argument("--choose", action="store_true", help="Datei-Auswahl immer anzeigen")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    src = Path(args.source_py).resolve() if args.source_py else pick_python_file(root, force_menu=args.choose)

    if not src.exists() or src.suffix.lower() != ".py":
        raise SystemExit("Fehler: source_py muss eine vorhandene .py-Datei sein.")

    py_dir = root / "android-chaquopy" / "app" / "src" / "main" / "python"
    if not py_dir.exists():
        raise SystemExit("Fehler: android-chaquopy Struktur fehlt.")

    ensure(py_dir)
    target = py_dir / args.target_name
    shutil.copy2(src, target)

    wrapper = py_dir / "game_core.py"
    wrapper.write_text(
        f'''# Auto-generiert von apk_builder.py
import importlib.util
from pathlib import Path

_module_path = Path(__file__).with_name("{args.target_name}")
_spec = importlib.util.spec_from_file_location("app_logic", _module_path)
app_logic = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(app_logic)


def hello():
    return "Python-Bridge aktiv"
''',
        encoding="utf-8",
    )

    workflow_path = root / ".github" / "workflows" / "build-apk-chaquopy.yml"
    ensure(workflow_path.parent)
    workflow_path.write_text(WORKFLOW_TEXT, encoding="utf-8")

    print("Fertig:")
    print(f"- Python kopiert nach: {target}")
    print(f"- Wrapper erstellt:   {wrapper}")
    print(f"- Workflow erstellt:  {workflow_path}")

    do_auto_git = args.auto_git or args.full_auto
    if not do_auto_git:
        print("\nNächster Schritt: git add/commit/push")
        return

    git = find_git(root, args.git_exe)
    if not git:
        raise SystemExit("Fehler: git wurde nicht gefunden.")

    if run([git, "add", "."], root) != 0:
        raise SystemExit("Fehler: git add fehlgeschlagen.")

    commit_rc = run([git, "commit", "-m", args.commit_msg], root)
    if commit_rc != 0:
        print("Hinweis: Kein neuer Commit (evtl. keine Änderungen).")

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
    wait_and_download_apk(repo, token, head_sha, root / args.out_dir)


if __name__ == "__main__":
    main()

from __future__ import annotations

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
          chmod +x gradlew || true
          gradle assembleDebug --stacktrace

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: app-debug-apk
          path: android-chaquopy/app/build/outputs/apk/debug/*.apk
          if-no-files-found: error
"""


CONFIG_FILE = "apk_builder_config.json"


def ensure(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def get_config_path(root: Path) -> Path:
    local = root / CONFIG_FILE
    if local.exists():
        return local
    if os.name == "nt":
        base = Path(os.getenv("APPDATA", str(Path.home())))
        return base / "apk_builder" / CONFIG_FILE
    return Path.home() / ".config" / "apk_builder" / CONFIG_FILE


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


def save_config(root: Path, repo: str | None, git_exe: str | None, token: str | None) -> None:
    cfg = get_config_path(root)
    ensure(cfg.parent)
    cfg.write_text(
        json.dumps({"repo": repo or "", "git_exe": git_exe or "", "token": token or ""}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run(cmd: list[str], cwd: Path) -> int:
    print(">", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(cwd)).returncode


def run_out(cmd: list[str], cwd: Path) -> str:
    return subprocess.check_output(cmd, cwd=str(cwd), text=True).strip()


def repo_rel(path: Path, root: Path) -> str | None:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\\\", "/")
    except Exception:
        return None


def find_git(root: Path, git_exe: str | None) -> str | None:
    if git_exe:
        candidate = Path(git_exe)
        if candidate.exists():
            return str(candidate)
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
    match = re.search(r"github\.com[:/]([^/]+/[^/.]+)(?:\.git)?$", url)
    return match.group(1) if match else None


def git_changed_paths(git: str, root: Path) -> list[str]:
    try:
        raw = run_out([git, "status", "--porcelain"], root)
    except Exception:
        return []
    out: list[str] = []
    for line in raw.splitlines():
        line = line.lstrip("ï»¿")
        if not line.strip():
            continue
        if len(line) >= 4 and line[2] == " ":
            entry = line[3:]
        else:
            parts = line.split(maxsplit=1)
            entry = parts[1] if len(parts) > 1 else ""
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        out.append(entry.replace("\\\\", "/").strip())
    return out


def workflow_meta() -> tuple[str, str, str]:
    return "build-apk-chaquopy.yml", "Build APK (Chaquopy)", CHAQUOPY_WORKFLOW_TEXT


def gh_api(repo: str, token: str, path: str) -> object:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}{path}",
        headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "apk-builder"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def download_binary(url: str, token: str, dest: Path) -> None:
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "apk-builder"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        dest.write_bytes(response.read())


def wait_and_download_apk(repo: str, token: str, head_sha: str, out_dir: Path, *, branch: str | None, timeout_sec: int = 1800, poll_sec: int = 15) -> tuple[Path, Path]:
    ensure(out_dir)
    workflow_file, workflow_name, _ = workflow_meta()
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        data = gh_api(repo, token, f"/actions/workflows/{workflow_file}/runs?per_page=20")
        runs = data.get("workflow_runs", []) if isinstance(data, dict) else []
        for item in runs:
            if item.get("head_sha") != head_sha:
                continue
            if branch and item.get("head_branch") not in {branch, None}:
                continue
            status = item.get("status")
            conclusion = item.get("conclusion")
            print(f"Workflow gefunden: {workflow_name} / Status={status} / Ergebnis={conclusion}")
            if status != "completed":
                break
            if conclusion != "success":
                raise SystemExit(f"Fehler: GitHub Workflow beendet mit Ergebnis '{conclusion}'.")
            run_id = item["id"]
            arts = gh_api(repo, token, f"/actions/runs/{run_id}/artifacts")
            artifacts = arts.get("artifacts", []) if isinstance(arts, dict) else []
            artifact = next((a for a in artifacts if not a.get("expired") and a.get("name") == "app-debug-apk"), None)
            if not artifact:
                raise SystemExit("Fehler: Kein APK-Artefakt gefunden.")
            zip_path = out_dir / f"artifact-{head_sha[:7]}.zip"
            download_binary(artifact["archive_download_url"], token, zip_path)
            extract_dir = out_dir / f"extract-{head_sha[:7]}"
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            ensure(extract_dir)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
            apk_files = sorted(extract_dir.rglob("*.apk"))
            if not apk_files:
                raise SystemExit("Fehler: ZIP geladen, aber keine APK enthalten.")
            apk_dest = out_dir / apk_files[0].name
            shutil.copy2(apk_files[0], apk_dest)
            return zip_path, apk_dest
        print("Warte auf GitHub-Build...")
        time.sleep(poll_sec)
    raise SystemExit("Fehler: Timeout beim Warten auf den GitHub-Build.")


def pick_python_file(root: Path) -> Path:
    files: list[Path] = []
    for path in sorted(root.glob("*.py"), key=lambda item: item.name.lower()):
        if path.name.lower() == "build.py":
            continue
        files.append(path)
    nested = root / "android-chaquopy" / "app" / "src" / "main" / "python" / "app_logic.py"
    if nested.exists():
        files.append(nested)
    unique: list[Path] = []
    seen: set[str] = set()
    for path in files:
        key = str(path.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    files = unique
    if not files:
        raise SystemExit("Fehler: Keine .py-Datei im Projektordner gefunden.")
    print("W?hle die Python-Datei f?r die APK:")
    for index, path in enumerate(files, 1):
        print(f"{index}) {path.relative_to(root) if path.is_relative_to(root) else path}")
    while True:
        choice = input(f"Nummer eingeben (1-{len(files)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(files):
            return files[int(choice) - 1]
        print("Ung?ltig. Bitte nochmal.")


def module_name_from_path(src: Path) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", src.stem)
    if not name or name[0].isdigit():
        name = f"app_{name}"
    return name


def bridge_text(module_filename: str) -> str:
    return f"""import importlib.util
import pathlib
import traceback

_module_path = pathlib.Path(__file__).resolve().parent / "{module_filename}"
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
            return "run_epoch Fehler:\n" + traceback.format_exc()
    if hasattr(app_logic, "main"):
        try:
            result = app_logic.main()
            return f"main() ausgef?hrt: {{result}}"
        except Exception:
            return "main() Fehler:\n" + traceback.format_exc()
    return "Keine run_epoch()/main() gefunden, aber Modul wurde geladen."
"""


def create_chaquopy_project(root: Path, src: Path, application_id: str, app_name: str) -> list[Path]:
    base = root / "android-chaquopy"
    app = base / "app"
    py_dir = app / "src" / "main" / "python"
    kt_dir = app / "src" / "main" / "java" / "com" / "example" / "apkbuilder"
    res_layout = app / "src" / "main" / "res" / "layout"
    res_values = app / "src" / "main" / "res" / "values"
    for directory in (py_dir, kt_dir, res_layout, res_values):
        ensure(directory)
    generated: list[Path] = []
    files = {
        base / "settings.gradle": """pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "AndroidChaquopyApp"
include(":app")
""",
        base / "build.gradle": """plugins {
    id "com.android.application" version "8.5.2" apply false
    id "org.jetbrains.kotlin.android" version "1.9.24" apply false
    id "com.chaquo.python" version "15.0.1" apply false
}
""",
        base / "gradle.properties": """org.gradle.jvmargs=-Xmx2g -Dfile.encoding=UTF-8
android.useAndroidX=true
android.nonTransitiveRClass=true
kotlin.code.style=official
""",
        base / "gradlew": """#!/usr/bin/env sh
gradle "$@"
""",
        app / "build.gradle": f"""plugins {{
    id "com.android.application"
    id "org.jetbrains.kotlin.android"
    id "com.chaquo.python"
}}

android {{
    namespace "{application_id}"
    compileSdk 34

    defaultConfig {{
        applicationId "{application_id}"
        minSdk 24
        targetSdk 34
        versionCode 1
        versionName "1.0"
        python {{
            version "3.11"
        }}
    }}

    buildTypes {{
        release {{
            minifyEnabled false
            proguardFiles getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro"
        }}
    }}

    compileOptions {{
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }}
    kotlinOptions {{
        jvmTarget = "17"
    }}
}}

dependencies {{
    implementation "androidx.core:core-ktx:1.13.1"
    implementation "androidx.appcompat:appcompat:1.7.0"
    implementation "com.google.android.material:material:1.12.0"
    implementation "androidx.constraintlayout:constraintlayout:2.1.4"
}}
""",
        app / "proguard-rules.pro": "",
        app / "src" / "main" / "AndroidManifest.xml": f"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application
        android:allowBackup="true"
        android:label="{app_name}"
        android:supportsRtl="true"
        android:theme="@style/Theme.MaterialComponents.DayNight.DarkActionBar">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
""",
        kt_dir / "MainActivity.kt": """package com.example.apkbuilder

import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }

        val status = findViewById<TextView>(R.id.statusText)
        val runButton = findViewById<Button>(R.id.runButton)
        val bridge = Python.getInstance().getModule("bridge")

        status.text = bridge.callAttr("get_status").toString()
        runButton.setOnClickListener {
            status.text = bridge.callAttr("run_epoch").toString()
        }
    }
}
""",
        res_layout / "activity_main.xml": f"""<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:padding="24dp">

    <TextView
        android:id="@+id/titleText"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="{app_name}"
        android:textSize="22sp"
        android:textStyle="bold" />

    <TextView
        android:id="@+id/statusText"
        android:layout_width="match_parent"
        android:layout_height="0dp"
        android:layout_weight="1"
        android:paddingTop="16dp"
        android:text="Initialisiere Python..."
        android:textSize="16sp" />

    <Button
        android:id="@+id/runButton"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:text="Python ausf?hren" />
</LinearLayout>
""",
        res_values / "strings.xml": f"""<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">{app_name}</string>
</resources>
""",
    }
    for path, text in files.items():
        ensure(path.parent)
        path.write_text(text, encoding="utf-8")
        generated.append(path)
    target_name = f"{module_name_from_path(src)}.py"
    target = py_dir / target_name
    shutil.copy2(src, target)
    generated.append(target)
    bridge = py_dir / "bridge.py"
    bridge.write_text(bridge_text(target.name), encoding="utf-8")
    generated.append(bridge)
    return generated


def main() -> None:
    root = Path(__file__).resolve().parent
    cfg = load_config(root)
    parser = argparse.ArgumentParser(description="Erstellt automatisch eine Chaquopy-APK ?ber GitHub Actions.")
    parser.add_argument("--python-file", help="Konkrete Python-Datei")
    parser.add_argument("--git-exe", help="Pfad zu git.exe")
    parser.add_argument("--repo", help="GitHub Repo: owner/name")
    parser.add_argument("--token", help="GitHub Token oder GH_TOKEN/GITHUB_TOKEN")
    parser.add_argument("--set-token", action="store_true", help="Gespeicherten Token neu eingeben")
    parser.add_argument("--out-dir", default="bin", help="Ausgabeordner f?r APK und ZIP")
    parser.add_argument("--no-download", action="store_true", help="Nicht auf die APK warten")
    parser.add_argument("--commit-msg", default="Add Android APK build files", help="Git Commit Nachricht")
    args = parser.parse_args()

    args.repo = args.repo or cfg.get("repo") or ""
    args.token = args.token or cfg.get("token") or ""
    args.git_exe = args.git_exe or cfg.get("git_exe") or ""

    if args.set_token:
        new_token = input("Neuen GitHub Token eingeben (leer = behalten): ").strip()
        if new_token:
            args.token = new_token

    git = find_git(root, args.git_exe or None)
    if git:
        args.git_exe = git
    if not args.repo and git:
        args.repo = parse_repo_from_origin(git, root) or ""
    if not args.repo:
        args.repo = input("GitHub Repo (owner/name): ").strip()
    if not args.token:
        args.token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN") or ""
    if not args.token:
        args.token = input("GitHub Token: ").strip()

    save_config(root, args.repo, args.git_exe, args.token)

    src = Path(args.python_file).resolve() if args.python_file else pick_python_file(root)
    if not src.exists():
        raise SystemExit(f"Fehler: Datei nicht gefunden: {src}")

    app_name = src.stem.replace("_", " ").replace("-", " ").strip().title() or "Python APK"
    generated_paths = create_chaquopy_project(root, src, "com.example.apkbuilder", app_name)

    workflow_filename, _, workflow_text = workflow_meta()
    workflow_path = root / ".github" / "workflows" / workflow_filename
    ensure(workflow_path.parent)
    workflow_path.write_text(workflow_text, encoding="utf-8")
    generated_paths.append(workflow_path)

    print("Fertig:")
    print(f"- Gew?hlte Python-Datei: {src}")
    print(f"- Workflow erstellt: {workflow_path}")
    print(f"- APK landet automatisch in: {root / args.out_dir}")

    if not git:
        raise SystemExit("Fehler: git wurde nicht gefunden.")

    stage_paths: list[str] = []
    for path in generated_paths + [src]:
        rel = repo_rel(path, root)
        if rel:
            stage_paths.append(rel)
    for rel in git_changed_paths(git, root):
        low = rel.lower()
        if "__pycache__" in low or low.endswith(".pyc"):
            continue
        if low.endswith((".apk", ".aab", ".zip", ".log", ".tmp", ".keystore", ".jks")):
            continue
        if rel == "build.py" or rel.startswith(".github/workflows/") or rel.startswith("android-chaquopy/"):
            stage_paths.append(rel)
    stage_paths = list(dict.fromkeys(stage_paths))
    if not stage_paths:
        raise SystemExit("Fehler: Keine g?ltigen Repo-Dateien zum Stagen gefunden.")

    if run([git, "add", "--", *stage_paths], root) != 0:
        raise SystemExit("Fehler: git add fehlgeschlagen.")
    commit_rc = run([git, "commit", "-m", args.commit_msg, "--", *stage_paths], root)
    if commit_rc != 0:
        print("Hinweis: Kein neuer Commit in den Build-Dateien.")
    if run([git, "push"], root) != 0:
        raise SystemExit("Fehler: git push fehlgeschlagen.")
    print("Push fertig. GitHub baut jetzt die APK.")

    if args.no_download:
        return

    head_sha = run_out([git, "rev-parse", "HEAD"], root)
    branch = run_out([git, "rev-parse", "--abbrev-ref", "HEAD"], root)
    zip_path, apk_path = wait_and_download_apk(repo=args.repo, token=args.token, head_sha=head_sha, out_dir=root / args.out_dir, branch=branch if branch != "HEAD" else None)

    print("")
    print("===== ERFOLG =====")
    print(f"ZIP gespeichert unter: {zip_path}")
    print(f"APK gespeichert unter: {apk_path}")
    print("==================")


if __name__ == "__main__":
    main()

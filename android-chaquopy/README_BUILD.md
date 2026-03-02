# Build (Windows, ohne WSL)

## 1) In Android Studio öffnen
- Ordner `android-chaquopy` öffnen.
- Sync abwarten.

## 2) Falls nach Java gefragt wird
- In Android Studio JDK 17 wählen.

## 3) APK bauen
- Menü: **Build -> Build APK(s)**
- oder Terminal im Ordner `android-chaquopy`:
  - `gradlew.bat assembleDebug`

## 4) Ergebnis
- APK: `app/build/outputs/apk/debug/app-debug.apk`

## Hinweis
- Das ist die Chaquopy-Version.
- Python läuft jetzt aus **`ai leanr walk.py`** (portiert nach `app/src/main/python/ai_leanr_walk.py`).
- Die Tkinter-Desktop-UI wurde durch eine Android-UI ersetzt.

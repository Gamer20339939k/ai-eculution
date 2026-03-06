# Speicher Dateimanager (Android + Python/Chaquopy)

Dieses Projekt enthält eine Android-App mit Kotlin-UI und Python-Logik (Chaquopy).

## Projektstruktur
- `android-chaquopy/` Android-App
- `android-chaquopy/app/src/main/java/...` Kotlin UI
- `android-chaquopy/app/src/main/python/` Python Logik
- `.github/workflows/build-apk-chaquopy.yml` CI Build

## Lokal bauen (Windows)
Siehe:
- `android-chaquopy/README_BUILD.md`

Kurz:
```bash
cd android-chaquopy
gradlew.bat assembleDebug
```

## Release-Ziel
- Stabiler Start ohne Crash
- Debug + Release Build in CI
- Python-Syntaxcheck vor APK-Build

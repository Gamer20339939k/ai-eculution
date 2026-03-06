# Build (Windows, ohne WSL)

## Voraussetzungen
- Android Studio
- JDK 17

## Debug APK bauen
1. Ordner `android-chaquopy` in Android Studio öffnen.
2. Projekt synchronisieren lassen.
3. Menü: **Build -> Build APK(s)**  
   oder im Terminal:
   ```bash
   gradlew.bat assembleDebug
   ```

Ergebnis:
- `app/build/outputs/apk/debug/app-debug.apk`

## Release APK bauen
Im Terminal:
```bash
gradlew.bat assembleRelease
```

Ergebnis:
- `app/build/outputs/apk/release/app-release-unsigned.apk`  
  (ohne Signatur)

## CI Build
GitHub Actions Workflow:
- `.github/workflows/build-apk-chaquopy.yml`
- Baut Debug + Release APK
- Prüft vorher Python-Dateien per `py_compile`

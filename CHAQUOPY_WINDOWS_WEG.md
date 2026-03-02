# APK unter Windows mit Chaquopy (ohne WSL)

## Wichtig
- Deine aktuelle App ist **Kivy** (`main.py`).
- Chaquopy kann Python ausführen, aber **nicht Kivy-UI direkt als Android-App**.
- Du kannst die **Python-Logik** weiter nutzen, die UI muss in Android (Kotlin/Java) gebaut werden.

## 1) Android Studio Projekt erstellen
1. Android Studio -> New Project -> Empty Activity
2. Min SDK: 24+

## 2) Chaquopy aktivieren
Im Projekt:
- `settings.gradle`:
```gradle
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
```

- `app/build.gradle`:
```gradle
plugins {
    id 'com.android.application'
    id 'org.jetbrains.kotlin.android'
    id 'com.chaquo.python'
}

android {
    namespace 'com.thilo.evocreatureai'
    compileSdk 34
    defaultConfig {
        applicationId "com.thilo.evocreatureai"
        minSdk 24
        targetSdk 34
        versionCode 1
        versionName "0.1.0"
        ndk { abiFilters "arm64-v8a", "armeabi-v7a" }
        python {
            pip {
                install "numpy"
            }
        }
    }
}
```

## 3) Python-Dateien einbinden
Lege an:
- `app/src/main/python/game_core.py`

Starte mit reiner Logik (ohne Kivy-Imports).

## 4) Aufruf aus Kotlin
In `MainActivity.kt`:
```kotlin
val py = com.chaquo.python.Python.getInstance()
val mod = py.getModule("game_core")
val result = mod.callAttr("hello")
```

## 5) Build
- Build -> Generate APK(s)
- oder in Terminal:
```bash
gradlew assembleDebug
```

APK liegt dann in:
`app/build/outputs/apk/debug/`

---

Wenn du willst, baue ich dir im nächsten Schritt direkt:
1) `game_core.py` aus deiner `main.py` heraus (ohne Kivy),
2) eine erste Kotlin-Bridge,
3) eine lauffähige Debug-Basis.

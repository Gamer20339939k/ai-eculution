[app]
title = Evo Creature AI
package.name = evocreatureai
package.domain = com.thilo
source.dir = .
source.include_exts = py,png,jpg,kv,json
version = 0.1.0
requirements = python3,kivy
orientation = landscape
fullscreen = 0
android.archs = arm64-v8a, armeabi-v7a
android.api = 33
android.minapi = 24
android.accept_sdk_license = True

# Release signing (replace with your real values)
android.release_artifact = apk
android.release_keystore = ./release.keystore
android.release_keystore_password = CHANGE_ME
android.release_keyalias = evocreatureai
android.release_keyalias_password = CHANGE_ME

[buildozer]
log_level = 2
warn_on_root = 1

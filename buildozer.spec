[app]
title = Deadpan
package.name = deadpan
package.domain = org.deadpan
source.dir = .
source.include_exts = py,png,json
source.exclude_dirs = tests,bin,build,dist,.venv,.github,.buildozer
version = 0.1.0

# The Anthropic SDK is NOT listed: its compiled dependencies don't build for Android.
# The app talks to the Claude API over plain HTTPS there instead (see deadpan/llm.py).
requirements = python3,kivy==2.3.1,certifi

orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1

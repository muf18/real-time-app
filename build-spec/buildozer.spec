[app]
title = CryptoChart
package.name = cryptochart
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,proto
version = 0.1.0

requirements = python3,kivy,numpy,pydantic,websockets,httpx,aiolimiter,aiofiles,protobuf,orjson,keyring,backoff,kivy-garden.graph

orientation = portrait
# AAB is preferred for Google Play Store [45]
android.release_artifact = aab

# Permissions
android.permissions = INTERNET

# Android API levels (update as needed)
android.api = 33
android.minapi = 21
android.sdk = 24
android.ndk = 25b

android.archs = arm64-v8a, armeabi-v7a

# Signing configuration will be added by the CI/CD pipeline
# android.release.keystore.file = /path/to/release.keystore
# android.release.keystore.alias = ...
# android.release.keystore.password = ...
# android.release.keyalias.password = ...
# android-flutter

The Android app, built in Flutter, on the Kotlin backend in `android/androidlib`.

- **Backend**: `androidlib`'s Kotlin (the accessibility service, block screen
  and store) is compiled in straight from `android/androidlib`; see
  `android/app/build.gradle.kts`. `MainActivity.kt` exposes it to Dart over a
  method channel (`com.angusblance.blocker/backend`).
- **App ID** `com.angusblance.blocker.flutter`.

```sh
flutter run                       # on a connected phone or emulator
flutter build apk --release --target-platform android-arm64
flutter analyze && flutter test   # what CI runs
```

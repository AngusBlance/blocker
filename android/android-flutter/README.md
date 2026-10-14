# android-flutter

The Android app rebuilt in Flutter: same screens, look and setup flow as
`android-mobile` (React Native), on the same Kotlin backend.

- **Backend**: `androidlib`'s Kotlin (the accessibility service, block screen
  and store) is compiled in straight from `android/androidlib`; see
  `android/app/build.gradle.kts`. Only its Expo bridge, `AndroidlibModule.kt`,
  is left out; `MainActivity.kt` exposes the same calls to Dart over a method
  channel (`com.angusblance.blocker/backend`).
- **App ID** `com.angusblance.blocker.flutter`, so it installs next to the
  React Native app. Its accessibility service is separate and has to be turned
  on by itself.

```sh
flutter run                       # on a connected phone or emulator
flutter build apk --release --target-platform android-arm64
flutter analyze && flutter test   # what CI runs
```

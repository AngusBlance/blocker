plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.angusblance.blockerflutter"

    // The blocking backend is androidlib's Kotlin, compiled straight from
    // android/androidlib; MainActivity's method channel exposes it to Dart.
    sourceSets["main"].java.srcDir("../../../androidlib/src/main/java")
    sourceSets["main"].res.srcDir("../../../androidlib/src/main/res")
    // androidlib's JVM unit tests (./gradlew :app:testDebugUnitTest).
    sourceSets["test"].java.srcDir("../../../androidlib/src/test/java")
    sourceSets["test"].resources.srcDir("../../../androidlib/src/test/resources")
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "com.angusblance.blocker.flutter"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        // 26 (Android 8.0) for java.time, which schedules use.
        minSdk = 26
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
    // Android's org.json is a stub in JVM unit tests; use the real one.
    testImplementation("org.json:json:20250517")
}

flutter {
    source = "../.."
}

plugins {
    id("com.android.application")
    id("kotlin-android")
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.lcloud.lcloud"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    kotlinOptions {
        jvmTarget = "11"
    }

    defaultConfig {
        applicationId = "com.lcloud.lcloud"
        minSdk = 29          // Android 10+ — all such devices are arm64
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        ndk {
            // arm64-v8a covers every Android 10+ device sold since ~2017.
            // Dropping armeabi-v7a and x86_64 removes ~21 MB from the APK.
            abiFilters += listOf("arm64-v8a")
        }
    }

    buildTypes {
        release {
            // Signed with debug key for prototype testing
            signingConfig = signingConfigs.getByName("debug")
            // Strip unused resources (Flutter's plugin handles code minification)
            isShrinkResources = true
            isMinifyEnabled = true
        }
    }
}

flutter {
    source = "../.."
}

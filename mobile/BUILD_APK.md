# SignalFlow Mobile - APK Build Guide

This guide explains how to build the SignalFlow mobile app APK for Android.

## Prerequisites

1. **Node.js** (v18 or later)
2. **Expo CLI** and **EAS CLI**
3. **Expo Account** (free at expo.dev)

### Install Required Tools

```bash
# Install EAS CLI globally
npm install -g eas-cli

# Login to Expo
eas login
```

## Quick Build Commands

### Development Build (for testing)

```bash
cd mobile
npm install --legacy-peer-deps
eas build --platform android --profile development
```

### Preview Build (internal testing)

```bash
eas build --platform android --profile preview
```

### Production Build (Play Store)

```bash
eas build --platform android --profile production
```

## Build Profiles

The build profiles are configured in `eas.json`:

| Profile | APK/AAB | Use Case |
|---------|---------|----------|
| `development` | APK | Local testing with dev client |
| `preview` | APK | Internal team testing |
| `production` | AAB | Google Play Store submission |

## Local APK Build (without EAS cloud)

To build locally without using EAS cloud services:

```bash
# Install dependencies
npm install --legacy-peer-deps

# Generate native Android project
npx expo prebuild --platform android

# Build APK locally (requires Android SDK)
cd android
./gradlew assembleRelease

# APK location
# android/app/build/outputs/apk/release/app-release.apk
```

## Environment Configuration

### Required Environment Variables

Create `mobile/.env` or set in EAS secrets:

```env
EXPO_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
EXPO_PUBLIC_API_URL=https://your-api-domain.com
```

### Setting EAS Secrets (for cloud builds)

```bash
eas secret:create --name SUPABASE_URL --value "https://your-project.supabase.co"
eas secret:create --name SUPABASE_ANON_KEY --value "your-anon-key"
```

## Build Output

After a successful EAS build:

1. Check build status: `eas build:list`
2. Download APK from the Expo dashboard or use the QR code
3. Install on Android device (enable "Install from unknown sources")

## Troubleshooting

### Common Issues

**"Metro bundler error"**
```bash
npx expo start --clear
```

**"Dependency conflict"**
```bash
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
```

**"EAS build failed"**
```bash
# Check build logs
eas build:view

# Re-run with verbose logging
eas build --platform android --profile preview --non-interactive
```

### Jest Test Issues (before build)

If tests fail due to React Native configuration:
```bash
# Tests are optional for APK build
npm run build  # Skip tests
```

## Version Management

Update version in `app.json`:

```json
{
  "expo": {
    "version": "1.0.0",
    "android": {
      "versionCode": 1
    }
  }
}
```

Increment `versionCode` for each Play Store upload.

## Build Timeline

| Build Type | Approximate Time |
|------------|------------------|
| Development | 10-15 minutes |
| Preview | 10-15 minutes |
| Production | 15-20 minutes |

---

## Quick Reference

```bash
# Full build workflow
cd mobile
npm install --legacy-peer-deps
eas build --platform android --profile preview

# Check build status
eas build:list --platform android
```

For iOS builds, see the [Expo iOS build documentation](https://docs.expo.dev/build/setup/).

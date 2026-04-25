# Lcloud

**Automatic WiFi backup from your Android phone to your Windows PC.**

No cloud. No internet. No account. Just your files, safe on your PC.

---

## What It Does

- Backs up photos, videos, WhatsApp media, and documents over your home WiFi
- Organizes everything neatly: `Photos/2026/04/`, `WhatsApp/Images/`, etc.
- Restores any backed-up file back to its exact original location on your phone
- Uses HTTPS with certificate fingerprint trust — secure, zero configuration

## What Makes It Different

Two features no other free backup app has:

1. **Smart Priority Engine** *(backlog)* — backs up WhatsApp media first, then newest photos, then videos, then documents.
2. **Storage Threshold Trigger** *(backlog)* — when your phone drops below 15% free, backup starts automatically.

## Current Status

| Version | Status | What It Has |
|---------|--------|-------------|
| v0.1 | ✅ Done | Manual backup, file organization, WiFi transfer |
| v0.2 | ✅ Done | Secure HTTPS transport, cert fingerprint trust, real progress |
| v0.3 | ✅ Done | File restore — browse sessions, pick files, restore to phone |
| v0.4 | Planned | AES-256-GCM at-rest encryption |
| v0.5 | Planned | Open source release, Windows auto-start |

## Quick Start

**PC:**
```bat
cd lcloud-pc
setup.bat    # first time only
run.bat      # start Lcloud
```

Or just double-click **`Lcloud.exe`**.

**Android:** Install `lcloud-android.apk` from the releases section, or build from source:
```bat
cd lcloud-android
flutter run
```

## How It Works

```
Your Phone (Android)                 Your PC (Windows)
──────────────────                   ─────────────────
Discovers PC on WiFi    ─────────►  PC broadcasts presence every 2s
Verifies PC identity               (multicast UDP on home WiFi)
via cert fingerprint

Taps "Backup Now"       ─────────►  PC receives files over HTTPS
Files stream to PC                  Files organized into folders

Taps "Restore"          ◄─────────  Manifests served via HTTPS
Picks files to restore              Files streamed back to phone
```

No IP typing. No pairing codes. Just open both apps and tap Backup Now.

## Project Structure

```
lcloud/
├── lcloud-pc/           Windows app (Python + CustomTkinter)
├── lcloud-android/      Android app (Flutter/Dart)
├── docs/
│   ├── VERSIONS.md      Version tracker — what's in each version, what's planned
│   ├── FEATURES.md      Feature brainstorming, backlog, competitor analysis
│   ├── ARCHITECTURE.md  Technical decisions, protocol details, tradeoffs
│   └── USER_GUIDE.md    How to install and use Lcloud
├── CHANGELOG.md         Detailed release notes
└── CLAUDE.md            Development context (for Claude Code sessions)
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Android app | Flutter (Dart) |
| Windows app | Python 3.12 + CustomTkinter |
| Device discovery | UDP multicast (224.0.0.167:53317) |
| File transfer | HTTPS with self-signed cert + fingerprint trust |
| Storage | Local only — your PC, your files |

## Contributing

This project is being built in the open. Contributions welcome once v0.5 releases.

## License

MIT — free to use, modify, share.

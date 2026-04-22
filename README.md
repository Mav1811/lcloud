# Lcloud

**Automatic WiFi backup from your Android phone to your Windows PC.**

No cloud. No internet. No account. Just your files, safe on your PC.

---

## What It Does

- Backs up photos, videos, WhatsApp media, and documents over your home WiFi
- Organizes everything neatly: `Photos/2026/04/`, `WhatsApp/Images/`, etc.
- Works over home WiFi — no cables, no internet required
- Uses HTTPS with certificate fingerprint trust — no setup for the user

## What Makes It Different

Two features no other free backup app has:

1. **Smart Priority Engine** *(coming v0.3)* — backs up WhatsApp media first, then newest photos, then videos, then documents. Not random.
2. **Storage Threshold Trigger** *(coming v0.3)* — when your phone is below 15% free, backup starts automatically. Set it and forget it.

## Current Status

| Version | Status | What It Has |
|---------|--------|-------------|
| v0.1 | ✅ Shipped | Manual backup, file organization, WiFi transfer |
| v0.2 | ✅ Shipped | Secure HTTPS transport, cert fingerprint trust, real progress tracking |
| v0.3 | 🔨 In Progress | File restore — browse backed-up files and restore to phone |
| v0.4 | Planned | AES-256-GCM at-rest encryption |
| v0.5 | Planned | Open source release, Windows auto-start |

## Quick Start

**PC:**
```bat
cd lcloud-pc
setup.bat    # first time only
run.bat      # start Lcloud
```

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
```

No IP typing. No pairing codes. Just open both apps and tap Backup Now.

## Project Structure

```
lcloud/
├── lcloud-pc/        Windows app (Python + CustomTkinter)
├── lcloud-android/   Android app (Flutter/Dart)
├── docs/             Guides, specs, research
│   ├── USER_GUIDE.md
│   ├── DEV_GUIDE.md
│   └── research/     Market analysis, competitor comparison
├── ROADMAP.md        Feature plan by version
└── CHANGELOG.md      What changed in each version
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Android app | Flutter (Dart) |
| Windows app | Python 3.12 + CustomTkinter |
| Device discovery | UDP multicast (224.0.0.167:53317) |
| File transfer | HTTPS with self-signed cert + fingerprint trust |
| Storage | Local only — your PC, your files |

## Build Environment

| Tool | Location |
|------|----------|
| Flutter 3.41.6 | `H:\fun\tools\flutter\bin` |
| JDK 17 | `H:\fun\tools\jdk-17.0.18+8` |
| Python 3.12 | System PATH |

## Contributing

This project is being built in the open. Contributions welcome once v0.5 releases.

## License

MIT — free to use, modify, share.

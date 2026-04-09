# Lcloud

**Automatic WiFi backup from your Android phone to your Windows PC.**

No cloud. No internet. No account. Just your files, safe on your PC.

---

## What It Does

- Automatically backs up your phone when storage gets low (below 15%)
- Backs up WhatsApp media, photos, videos, and documents
- Organizes everything neatly: `Photos/2025/04/`, `WhatsApp/Images/`, etc.
- Backs up important stuff first (WhatsApp → Photos → Videos → Documents)
- Works over your home WiFi — no cables, no internet

## What Makes It Different

Two features no other backup app has:

1. **Smart Priority Engine** — backs up your WhatsApp media first, then newest photos, then videos, then documents. Not random.
2. **Storage Threshold Trigger** — when your phone is below 15% free, backup starts automatically. Set it and forget it.

## Quick Start

See [docs/USER_GUIDE.md](docs/USER_GUIDE.md) for full setup instructions.

**Short version:**
1. Install Python 3.12 (check "Add to PATH")
2. Run `lcloud-pc/setup.bat`
3. Install Flutter → run `tools/install_flutter.bat`
4. Build Android app: `cd lcloud-android && flutter run`
5. Start PC app: `lcloud-pc/run.bat`

## Project Structure

```
lcloud/
├── lcloud-pc/        Windows app (Python + CustomTkinter)
├── lcloud-android/   Android app (Flutter/Dart)
├── docs/             User guide, developer guide, design spec
├── tools/            Setup scripts
├── ROADMAP.md        Feature plan by version
└── CHANGELOG.md      What changed in each version
```

## Version

**Current: v0.1.0** — Working prototype. Manual backup, file organization, WiFi transfer.

See [ROADMAP.md](ROADMAP.md) for what's coming.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Android app | Flutter (Dart) |
| Windows app | Python 3.12 + CustomTkinter |
| Device discovery | mDNS / Zeroconf |
| File transfer | HTTP over local WiFi |
| Storage | Local only — your PC, your files |

## License

MIT — free to use, modify, share.

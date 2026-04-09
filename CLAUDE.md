# Lcloud — Claude Project File

> **How to use this file:** Update the `## Current Tasks` section to tell Claude what to work on next.
> When resuming a session just say "resume the project" — Claude will read this file first.

---

## Current Tasks

<!-- ADD / EDIT TASKS HERE — Claude reads this at the start of every session -->

### v0.1 — Done ✅
- [x] PC app complete and working (run with lcloud-pc/run.bat)
- [x] Android APK built (lcloud-android.apk at project root — rebuild with build-android.bat)
- [x] Disk space check — PC warns and rejects backup if not enough space (Q14)
- [x] Settings panel on PC — gear button to configure port (Q23)
- [x] Clear error messages for disk full, no folder set

### v0.2 — Next
- [ ] Implement smart priority engine (WhatsApp → Photos → Videos → Docs)
- [ ] Implement storage threshold trigger (phone below 15% free → auto-backup)
- [ ] Add "Delete after backup?" — actually execute the delete (currently shows "coming in v0.3")
- [ ] Progress bar with speed + ETA on both sides

---

## Project Overview

**Lcloud** = automatic WiFi backup from Android phone to Windows PC.
No cloud, no internet, no account. Files stay local.

**Two killer features** (not in any competitor):
1. **Priority engine** — WhatsApp first, then newest photos, then videos, then docs
2. **Storage threshold trigger** — phone hits 15% free → backup starts automatically

**Current version:** v0.1.0 — full prototype working. Manual backup only.
**Next milestone:** v0.2.0 — priority engine + auto-trigger.

---

## Build Environment

| Tool | Location | Notes |
|------|----------|-------|
| Flutter 3.41.6 | `H:\fun\tools\flutter\bin` | Add to PATH or use full path |
| JDK 17 (Microsoft) | `H:\fun\tools\jdk-17.0.18+8` | Flutter configured to use this via `flutter config --jdk-dir` |
| Android SDK | `C:\Users\{user}\AppData\Local\Android\Sdk` | Already set up |
| Python 3.12 | System PATH | Used for PC app |

---

## How to Run

### PC App
```bat
cd lcloud-pc
setup.bat          # first time only — creates venv, installs deps
run.bat            # start the app
```

### Android App
```bat
tools\install_flutter.bat    # first time only
cd lcloud-android
flutter run                  # build + deploy to connected device
```

### Tests
```bat
cd lcloud-pc
call venv\Scripts\activate
pytest tests\ -v
```

---

## Architecture

```
Android (Flutter/Dart)               Windows PC (Python 3.12)
──────────────────────               ────────────────────────
FileScanner                          BackupEngine
  └─ scans storage by priority   →     └─ HTTP server on port 52000
  └─ builds ordered file list          └─ receives file list (POST /announce)
                                        └─ downloads each file (GET /file/...)
LcloudHttpServer (port 52001)        FileOrganizer
  └─ serves files as byte streams  →    └─ sorts into Photos/Videos/WhatsApp/Docs
                                        └─ creates year/month subfolders
LcloudDiscovery                      LcloudDiscovery
  └─ mDNS advertise + find PC    ↔    └─ mDNS register + find phone
```

**Ports:** PC listens on `52000`, Phone serves on `52001`
**mDNS service name:** `_lcloud._tcp.local.`
**Settings stored:** `%LOCALAPPDATA%\lcloud\settings.json`
**Log file:** `%LOCALAPPDATA%\lcloud\lcloud.log`

---

## File Map

```
lcloud/
├── CLAUDE.md              ← YOU ARE HERE — tasks + project context
├── README.md              ← public-facing overview
├── ROADMAP.md             ← version plan (v0.1 → v0.5+)
├── CHANGELOG.md           ← what shipped in each version
├── .gitignore
│
├── docs/
│   ├── USER_GUIDE.md      ← setup + usage instructions for end users
│   ├── DEV_GUIDE.md       ← architecture, dev setup, known gaps
│   └── specs/
│       └── lcloud-design.md  ← full design spec (answered Q1-16)
│
├── lcloud-pc/             ← Windows app (Python)
│   ├── src/
│   │   ├── main.py        ← entry point, wires everything together
│   │   ├── config.py      ← ALL constants + Settings class (single source of truth)
│   │   ├── core/
│   │   │   ├── backup_engine.py   ← HTTP server, orchestrates downloads
│   │   │   ├── file_organizer.py  ← sorts files into folders by type + date
│   │   │   └── discovery.py       ← mDNS: registers PC, finds phone
│   │   └── ui/
│   │       ├── main_window.py     ← CustomTkinter window
│   │       └── tray.py            ← system tray icon + menu
│   ├── tests/
│   │   ├── test_backup_engine.py
│   │   └── test_file_organizer.py
│   ├── requirements.txt
│   ├── setup.bat          ← creates venv + installs requirements
│   └── run.bat            ← activates venv + starts app
│
├── lcloud-android/        ← Android app (Flutter/Dart)
│   ├── lib/
│   │   ├── main.dart      ← entry point, permissions, MaterialApp
│   │   ├── models/
│   │   │   ├── backup_file.dart     ← data class for a file to transfer
│   │   │   └── backup_session.dart  ← data class for a completed session
│   │   ├── services/
│   │   │   ├── file_scanner.dart    ← scans storage, returns priority-ordered list
│   │   │   ├── http_server.dart     ← serves files to PC (shelf package)
│   │   │   └── discovery.dart       ← mDNS advertise + PC discovery
│   │   ├── screens/
│   │   │   ├── home_screen.dart     ← main UI + "Backup Now" button
│   │   │   └── settings_screen.dart ← settings (threshold, etc.)
│   │   └── widgets/
│   │       ├── status_card.dart     ← PC connection status
│   │       └── progress_card.dart   ← transfer progress display
│   ├── android/app/src/main/AndroidManifest.xml
│   ├── pubspec.yaml
│   └── analysis_options.yaml
│
└── tools/
    └── install_flutter.bat   ← one-time Flutter SDK setup for Windows
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| HTTP over local WiFi | Simple, no NAT issues, works on every router |
| mDNS for discovery | Zero-config — no IP typing, no pairing |
| Python + CustomTkinter | Fast to build, runs on any Windows without install |
| Flutter for Android | Cross-platform future (iOS later), good HTTP/mDNS packages |
| All config in `config.py` | Single source of truth — no magic strings elsewhere |
| Background thread for backup | UI never freezes; all UI updates via `window.after()` |
| `%LOCALAPPDATA%` for data | Correct Windows path for per-user app data |

---

## v0.2 Implementation Notes

When building v0.2, key files to touch:

**Priority engine:**
- `lcloud-android/lib/services/file_scanner.dart` — change sort order
- `lcloud-pc/src/core/backup_engine.py` — respect the order from the phone's file list

**Storage threshold trigger:**
- `lcloud-android/lib/services/file_scanner.dart` — add storage check method
- `lcloud-android/lib/screens/home_screen.dart` — add background polling / trigger logic
- `lcloud-android/lib/screens/settings_screen.dart` — add threshold slider (default 15%)

**Progress bar with ETA:**
- `lcloud-pc/src/core/backup_engine.py` — emit progress callbacks with bytes/sec
- `lcloud-pc/src/ui/main_window.py` — wire progress to CTkProgressBar
- `lcloud-android/lib/widgets/progress_card.dart` — show speed + ETA on phone

---

## Version Status

| Version | Status | Focus |
|---------|--------|-------|
| v0.1 | ✅ Done | Working prototype — manual backup, file org, WiFi transfer |
| v0.2 | 🔨 Next | Priority engine + storage threshold trigger |
| v0.3 | Planned | Duplicate detection, resume, reliability |
| v0.4 | Planned | Encryption (AES-256-GCM + TLS) |
| v0.5 | Planned | Open source release, Windows service, APK |

---

## Conventions

- **Python style:** no type: ignore, all public methods typed, logging not print
- **Dart style:** follow `analysis_options.yaml`, prefer `final` everywhere
- **Tests:** write tests for all core logic (`lcloud-pc/tests/`)
- **Commits:** `feat(vX.Y): description` / `fix: description` / `chore: description`
- **Never commit:** `venv/`, `__pycache__/`, `*.log`, build artifacts

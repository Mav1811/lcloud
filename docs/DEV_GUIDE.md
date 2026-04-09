# Lcloud — Developer Guide
**For contributors and anyone who wants to understand how it works**

---

## Architecture Overview

```
Android (Flutter)                    Windows PC (Python)
─────────────────                    ─────────────────────
FileScanner                          BackupEngine
  └─ Scans all storage           ←→   └─ HTTP server on port 52000
  └─ Orders by priority               └─ Receives file list from phone
                                       └─ Downloads each file
LcloudHttpServer                      FileOrganizer
  └─ Serves files on port 52001   →    └─ Sorts files into folders
                                       └─ Handles name collisions
LcloudDiscovery                       LcloudDiscovery
  └─ Announces via mDNS           ←→   └─ Listens for phone on mDNS
  └─ Finds PC on network               └─ Registers itself on network

HomeScreen / SettingsScreen           MainWindow / TrayIcon
  └─ Flutter UI                        └─ CustomTkinter UI
```

---

## How the Backup Flow Works (v0.1)

1. **PC starts** → registers `_lcloud._tcp.local.` mDNS service on port 52000
2. **Phone starts** → scans for `_lcloud._tcp.local.` services → finds PC
3. **User taps "Backup Now"** on phone
4. Phone starts its own HTTP server on port 52001
5. Phone announces itself to PC: `POST /announce` with JSON file list
6. PC responds `{"ready": true}`
7. PC downloads each file: `GET /file/{encoded_path}` from phone's server
8. Each file is saved through FileOrganizer into the backup folder
9. Progress reported to UI via callbacks
10. Completion: PC sends `{"done": true}`, phone shows completion dialog

---

## PC App Structure

```
lcloud-pc/
├── src/
│   ├── main.py            ← Entry point, wires everything together
│   ├── config.py          ← All constants and settings (one place)
│   ├── ui/
│   │   ├── main_window.py ← The CustomTkinter window
│   │   └── tray.py        ← System tray icon + menu
│   └── core/
│       ├── backup_engine.py   ← HTTP server, coordinates downloads
│       ├── file_organizer.py  ← Sorts files into folders by type/date
│       └── discovery.py       ← mDNS: finds phone, registers PC
├── tests/
│   ├── test_file_organizer.py
│   └── test_backup_engine.py
└── requirements.txt
```

### Key design decisions
- **Threads**: Backup engine runs in a background thread. UI runs on main thread. All UI updates go through `window.after(0, callback)` to be thread-safe.
- **No global state**: Everything flows through class instances passed at construction time.
- **Logging**: Use Python's `logging` module everywhere. Log file: `AppData/Local/lcloud/lcloud.log`
- **Settings**: Stored as JSON in `AppData/Local/lcloud/settings.json`. Loaded at startup, saved on change.

---

## Android App Structure

```
lcloud-android/lib/
├── main.dart              ← Entry point, MaterialApp + permissions
├── models/
│   ├── backup_file.dart   ← Data class for a file to back up
│   └── backup_session.dart← Data class for a completed backup session
├── services/
│   ├── file_scanner.dart  ← Scans storage, returns ordered file list
│   ├── http_server.dart   ← Serves files to PC via HTTP (shelf)
│   └── discovery.dart     ← mDNS advertise + find PC
├── screens/
│   ├── home_screen.dart   ← Main UI
│   └── settings_screen.dart← Settings
└── widgets/
    ├── status_card.dart   ← Shows PC connection status
    └── progress_card.dart ← Shows transfer progress
```

### Key design decisions
- **Permissions**: All file permissions requested at app startup. On Android 11+, needs MANAGE_EXTERNAL_STORAGE → opens Settings page.
- **HTTP server**: `shelf` package runs the file server. Files served as byte streams.
- **mDNS**: `multicast_dns` package handles service discovery. Must request CHANGE_WIFI_MULTICAST_STATE permission.
- **State**: Simple `setState` for v0.1. Provider/Riverpod considered overkill at this stage.

---

## Running Tests

### PC tests
```bash
cd H:\fun\lcloud\lcloud-pc
call venv\Scripts\activate
pytest tests/ -v
```

### Android tests
```bash
cd H:\fun\lcloud\lcloud-android
flutter test
```

---

## Known Gaps in v0.1

These are tracked and scheduled for future versions:

| Gap | Severity | Version |
|-----|---------|---------|
| No encryption (files transfer in plain HTTP over local WiFi) | Medium | v0.4 |
| No duplicate detection (same file backed up twice) | Medium | v0.3 |
| No storage threshold trigger | High (core feature) | v0.2 |
| No priority engine | High (core feature) | v0.2 |
| No delete-after-backup | Medium | v0.2 |
| No backup history | Low | v0.3 |
| No Windows auto-start | Low | v0.5 |
| mDNS may fail on some routers with multicast filtering | Medium | v0.3 |
| Large files (>1GB) may timeout on slow WiFi | Low | v0.3 |
| No progress resume on interrupted backup | Medium | v0.3 |

---

## Adding a Feature

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Write tests first (see tests/ folder for examples)
3. Implement the feature
4. Run tests: `pytest tests/ -v` (PC) or `flutter test` (Android)
5. Update CHANGELOG.md
6. Submit PR on GitHub

---

## Common Issues

**mDNS not finding device:**
- Make sure both devices are on the same WiFi network (not one on WiFi, one on Ethernet)
- Some routers block multicast. Fallback: user types phone IP manually (v0.3 feature)
- Windows Firewall may block port 52000 — check firewall rules

**FileOrganizer putting files in wrong folder:**
- Check `config.py` extension lists
- Run `pytest tests/test_file_organizer.py -v` to see what's failing

**Android build failing:**
- Run `flutter doctor` — it tells you exactly what's missing
- Make sure Android SDK is at `C:\Users\{user}\AppData\Local\Android\Sdk`

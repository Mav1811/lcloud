# Lcloud Changelog

All notable changes to this project will be documented in this file.
Format: [Version] - Date | What changed

---

## [0.1.0] - 2026-04-09

### Added
- PC app: system tray icon with "Open" and "Quit" menu
- PC app: main window with backup status, folder picker, progress display
- PC app: mDNS service registration (announces PC on WiFi)
- PC app: HTTP server receives file list from phone
- PC app: downloads files from phone's HTTP server
- PC app: FileOrganizer sorts files into Photos/Videos/WhatsApp/Documents/Other
- PC app: date-based sub-folders (year/month)
- PC app: filename collision prevention
- Android app: home screen with backup status and "Backup Now" button
- Android app: file scanner (photos, videos, WhatsApp, documents)
- Android app: HTTP server serves files to PC (shelf)
- Android app: mDNS advertisement + PC discovery
- Android app: settings screen (coming in 0.2)
- Setup scripts: setup.bat, run.bat, install_flutter.bat

### Known limitations in 0.1.0
- No encryption (planned for v0.4)
- No duplicate detection (planned for v0.3)
- No storage threshold trigger (planned for v0.2)
- No priority engine active yet (planned for v0.2)
- No backup history (planned for v0.3)

---

## [0.2.0] - TBD

### Planned
- Smart priority engine: WhatsApp → Photos → Videos → Documents → Other
- Storage threshold trigger (default 15% free → auto-backup)
- "Delete after backup?" prompt on phone
- Progress bar with speed and ETA
- Low storage warning on PC UI

---

## [0.3.0] - TBD

### Planned
- Duplicate file detection (SHA-256)
- Resume interrupted backups
- Backup history log
- Retry on failure (3 attempts)
- mDNS fallback: manual IP input

---

## [0.4.0] - TBD

### Planned
- AES-256-GCM encryption at rest
- Password protection (PBKDF2)
- HTTPS/TLS for transfer

---

## [0.5.0] - TBD

### Planned
- Windows background service (auto-start)
- Full settings screen
- Notification toasts
- GitHub open source release
- Android APK release build

# Lcloud Changelog

All notable changes documented here.  
Format: `[Version] — Date | What changed`

---

## [0.3.0] — In Progress

### In Progress
- File restore: browse backed-up sessions on phone, select files, restore to original location
- Manifest writing: PC writes `{backup_root}/.lcloud/manifests/{session_id}.json` after each backup
- Three new restore endpoints: GET /restore/sessions, /restore/files, /restore/file
- RestoreScreen: category tabs, expandable sessions, file checkboxes, progress, summary

---

## [0.2.0] — 2026-04-22

### Replaced (Breaking — architectural rewrite)
- Old: mDNS (Zeroconf) discovery + PC pulls files from phone's HTTP server
- New: Multicast UDP discovery + phone pushes files to PC's HTTPS server

### Added
- **Self-signed TLS certificate** generated on first run (`%LOCALAPPDATA%\lcloud\lcloud.crt/key`)
- **SHA-256 fingerprint trust (TOFU)** — Android verifies PC cert by fingerprint, no CA needed
- **UDP multicast discovery** — PC broadcasts to `224.0.0.167:53317` every 2s, phone listens
- **HTTPS backup server** on port 53317 — session-based, one-time tokens per file
- **Real streaming upload** — files stream from phone to PC in 65536-byte chunks (never fully loaded into memory)
- **Real per-file progress** — `onProgress` callback gives actual bytes sent, not an estimate
- **Android multicast lock** — platform channel `com.lcloud.lcloud/multicast` prevents WiFi sleep during discovery
- Cert module: `lcloud-pc/src/core/certs.py` with 6 unit tests
- Transfer client: `lcloud-android/lib/services/transfer_client.dart`
- Windows path bug fix in `file_organizer.py` — phone paths like `/DCIM/photo.jpg` no longer replace the dest directory

### Removed
- `zeroconf` Python package (mDNS)
- `requests` Python package (HTTP pull)
- `lcloud-android/lib/services/http_server.dart` (phone no longer serves files)

### Tests
- PC: 8 tests for backup engine (info endpoint, prepare-upload, upload, cancel)
- PC: 6 tests for certificate generation and fingerprint
- Android: 5 tests for TransferClient and TransferFile

---

## [0.1.0] — 2026-04-09

### Added
- PC app: system tray icon with "Open" and "Quit" menu
- PC app: main window with backup status, folder picker, progress display
- PC app: mDNS service registration (announces PC on WiFi)
- PC app: HTTP server receives file list from phone
- PC app: downloads files from phone's HTTP server
- PC app: FileOrganizer sorts files into Photos/Videos/WhatsApp/Documents/Other with date sub-folders
- PC app: filename collision prevention
- Android app: home screen with backup status and "Backup Now" button
- Android app: file scanner (photos, videos, WhatsApp, documents)
- Android app: HTTP server serves files to PC (shelf)
- Android app: mDNS advertisement + PC discovery
- Setup scripts: setup.bat, run.bat, install_flutter.bat

### Known limitations in 0.1.0
- No encryption (v0.4)
- No duplicate detection (v0.3)
- No storage threshold trigger (v0.3)
- No priority engine (v0.3)
- No backup history (v0.3)
- mDNS unreliable on Windows (fixed in v0.2 with multicast UDP)

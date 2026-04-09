# Lcloud — Design Specification
**Version:** 0.1 (Prototype)  
**Date:** 2026-04-09  
**Status:** Approved by user (answers in my_answers.txt Q1–16)

---

## 1. What Is Lcloud?

A **WiFi-based automatic backup tool** that transfers files from your Android phone to your Windows PC over your home network — no internet, no cloud, no account, completely free and open source.

### Unique differentiators (no competitor has both)
1. **Smart Priority Engine** — backs up WhatsApp media first, then Photos (newest → oldest), then Videos, then Documents. Not random order.
2. **Storage Threshold Trigger** — Android app monitors free storage. When it drops below 15% (configurable), backup starts automatically.

### Closest competitor: LocalSend
LocalSend is open-source, WiFi file transfer, Flutter — but it is a **general-purpose file sender**, not a backup tool. It has no priority engine, no automatic trigger, no organized folder structure, and no backup history. Lcloud's audience is "I want my phone backed up automatically" not "I want to send a file to my laptop".

---

## 2. Architecture

```
┌──────────────────────────────────────────┐
│           Android Phone (Flutter)         │
│  ┌───────────────┐  ┌──────────────────┐ │
│  │  File Scanner │  │   HTTP Server    │ │
│  │  (priority    │  │   (shelf pkg)    │ │
│  │   ordering)   │  │   port 52000     │ │
│  └───────────────┘  └──────────────────┘ │
│  ┌─────────────────────────────────────┐  │
│  │  Storage Monitor (StatFs API)       │  │
│  │  threshold: 15% free → auto-backup  │  │
│  └─────────────────────────────────────┘  │
└──────────────────────────────────────────┘
              │  Local WiFi (HTTP)
              │  Auto-discovered via mDNS
              ▼
┌──────────────────────────────────────────┐
│           Windows PC (Python)             │
│  ┌───────────────┐  ┌──────────────────┐ │
│  │  mDNS         │  │  File Receiver   │ │
│  │  Discovery    │  │  (downloads from │ │
│  │  (zeroconf)   │  │   phone server)  │ │
│  └───────────────┘  └──────────────────┘ │
│  ┌───────────────┐  ┌──────────────────┐ │
│  │  File         │  │  UI: Tray Icon + │ │
│  │  Organizer    │  │  Main Window     │ │
│  │  (type/date)  │  │  (CustomTkinter) │ │
│  └───────────────┘  └──────────────────┘ │
└──────────────────────────────────────────┘
```

---

## 3. Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Android app | Flutter (Dart) | Free, open source, one codebase, future iOS possible |
| PC app | Python 3.12 | Readable, huge ecosystem, easy for contributors |
| PC UI | CustomTkinter | Modern look, dark mode, no paid license |
| PC tray | pystray | Industry standard for Python tray apps |
| Device discovery | mDNS via zeroconf (PC) + multicast_dns (Flutter) | No manual IP entry, like printers finding each other |
| File transfer | HTTP over local WiFi | Simple, fast, no special firewall rules |
| Encryption (v0.4+) | AES-256-GCM at rest, TLS in transit | Industry standard |
| Version control | Git + GitHub | Open source hosting |

---

## 4. Version Roadmap

### v0.1 — Working Prototype (current)
**Goal:** End-to-end file transfer works. Ugly is fine, broken is not.

PC side:
- [x] Tray icon (shows app is running)
- [x] Main window with clean UI
- [x] Folder picker (choose backup destination)
- [x] mDNS device discovery (finds phone on WiFi)
- [x] HTTP file receiver (downloads files from phone)
- [x] Basic file organizer (Photos / Videos / Documents / WhatsApp / Other)

Android side:
- [x] App with home screen showing backup status
- [x] Storage permissions (READ_EXTERNAL_STORAGE, MANAGE_EXTERNAL_STORAGE)
- [x] File scanner (finds all files on device)
- [x] HTTP server (serves files to PC)
- [x] "Backup Now" button
- [x] mDNS advertisement (announces itself on network)
- [x] WhatsApp media detection

**NOT in v0.1:** Encryption, storage trigger, priority engine, delete-after-backup, history

---

### v0.2 — Smart Engine
- Priority ordering: WhatsApp → Photos (newest first) → Videos → Documents → Other
- Storage threshold monitor (15% → auto-trigger)
- "Delete after backup?" prompt on phone
- Low storage warning on PC and phone
- Progress bar with file count and bytes transferred
- Transfer speed display

---

### v0.3 — Reliability
- Duplicate file detection (SHA-256 hash comparison)
- Resume interrupted backups (skip already-transferred files)
- Backup history log (date, files backed up, size)
- Retry on connection failure (3 attempts with backoff)
- Proper error messages on both sides

---

### v0.4 — Security
- AES-256-GCM encryption for files at rest on PC
- Password protection (PBKDF2 key derivation, 600,000 iterations)
- TLS/HTTPS for file transfer (self-signed cert, like LocalSend)
- Encrypted backup folder structure

---

### v0.5 — Release Ready
- Windows background service (auto-start with Windows, no window needed)
- Settings screen (change port, threshold %, backup folder, dark/light mode)
- Notification toasts (backup complete, errors)
- Backup statistics dashboard
- GitHub repo polish: README, contributing guide, issue templates
- Android APK release build

---

## 5. File Organization on PC

```
[Chosen Backup Folder]/
├── Photos/
│   ├── 2024/
│   │   ├── 03/
│   │   └── 04/
│   └── 2025/
├── Videos/
│   └── 2025/
├── WhatsApp/
│   ├── Images/
│   ├── Video/
│   ├── Audio/
│   └── Documents/
├── Documents/
│   └── 2025/
└── Other/
    └── 2025/
```

Files are named: `original-filename_YYYYMMDD_HHMMSS.ext` to prevent collisions.

---

## 6. Communication Protocol

```
1. PC starts → registers mDNS service "_lcloud._tcp.local" on port 52000
2. Android app starts → scans for "_lcloud._tcp.local" services
3. Android finds PC → displays "PC Found: [PC name]"
4. User taps "Backup Now" (or storage threshold triggers)
5. Android starts HTTP server on port 52001
6. Android sends POST to PC at port 52000: { "files": [...], "total_size": N }
7. PC responds: { "ready": true, "session_id": "uuid" }
8. PC connects to Android HTTP server, downloads each file
9. Android sends progress updates, PC shows in UI
10. Backup complete → PC sends { "done": true, "files_saved": N }
11. Android shows "Backup complete" + "Delete backed up files?" prompt
```

---

## 7. Key Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| HTTP vs raw TCP | HTTP | Simpler, better tooling, easier to debug |
| PC pulls vs Android pushes | PC pulls from Android server | Android running server is simpler than managing push targets |
| CustomTkinter vs PyQt6 | CustomTkinter | No GPL license concern, simpler, looks great for this use case |
| Dart/Flutter vs React Native | Flutter | Better performance, one codebase, spec already decided |
| Encryption in v1 | No, v0.4 | Speed of prototype, local WiFi is reasonably safe for now |

---

## 8. Open Questions (see my_answers.txt Q17–23)

- Python not installed → need user to install or choose portable mode
- Flutter not installed → need user to choose install location
- Min Android SDK version (defaulting to API 26 / Android 8)
- Real phone vs emulator for testing
- Auto-start with Windows (v0.5 feature, needed answer for setup)
- Encryption in v1 (defaulting to: No, skip for prototype)
- Port number (defaulting to 52000/52001)

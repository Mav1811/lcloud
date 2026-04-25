# Lcloud — Version Tracker

**Single source of truth for what's built, what's shipping next, and what's planned.**

---

## Current Version: v0.3 ✅

| Component | Status |
|-----------|--------|
| PC backup server (HTTPS push, multicast discovery) | ✅ Working |
| Android backup client (file scan, upload, progress) | ✅ Working |
| File restore (browse sessions, pick files, restore to phone) | ✅ Working |
| Lcloud.exe (Windows) | ✅ Built |
| lcloud-android.apk | ✅ Built |

---

## Version History

### v0.1 — Prototype · 2026-04-09 · ✅ Done

First end-to-end working build. Not production-ready — transport was broken and has since been replaced.

**What it had:**
- PC app: system tray, main window, folder picker
- File organizer: sorts files into `Photos/Videos/WhatsApp/Documents/Other` with date sub-folders
- Android app: file scanner, Backup Now button, backup history screen
- Transport: mDNS discovery (Zeroconf) + PC pulls files from phone's HTTP server

**Why it was replaced:** mDNS unreliable on Windows Firewall. PC-pull model gave fake progress. No encryption.

---

### v0.2 — Secure Transport · 2026-04-22 · ✅ Done

Full architectural rewrite of the transport layer. Everything about how phone and PC communicate was replaced.

**What changed:**
- Discovery: replaced mDNS with UDP multicast to `224.0.0.167:53317`
- Direction: replaced PC-pull with phone-push (HTTPS POST)
- Security: added self-signed RSA-2048 cert + SHA-256 fingerprint trust (TOFU, no CA)
- Progress: real per-file progress via streaming (65536-byte chunks, actual bytes sent)
- Cancel: `POST /cancel` endpoint cleans up session on abort
- Android: multicast lock platform channel prevents WiFi sleep during discovery

**Removed:** `zeroconf` package, `requests` package, phone-side HTTP server

---

### v0.3 — Restore · 2026-04-25 · ✅ Done

Files can now flow back from PC to phone. First version with full round-trip capability.

**What was added:**
- Manifest written after every completed backup: `{backup_root}/.lcloud/manifests/{session_id}.json`
  - Records `originalPath` (phone path) and `backedUpPath` (relative path on PC) per file
- Three new GET endpoints on the HTTPS server:
  - `GET /restore/sessions` — list all sessions with file counts and sizes
  - `GET /restore/files?sessionId&category` — file listing with one-time download tokens
  - `GET /restore/file?sessionId&fileId&token` — stream file back to phone
- RestoreScreen on Android: category tabs, expandable session rows, file checkboxes, Select All, restore progress
- Missing folder handling: dialog prompts per unique missing folder (Create / Use Lcloud_Restored/)
- Skip logic: files that already exist at original path are skipped (no overwrites)
- Summary view after restore: restored / skipped / failed counts, Retry Failed button
- Restore button on HomeScreen (disabled until PC is discovered)

**Tests added:** 13 RestoreHandler tests, 7 endpoint tests, 8 Android data class tests (28 total, 70 across project)

---

## Upcoming Versions

### v0.4 — Security · Planned

Encryption for files at rest on the PC. TLS in-transit is already done (v0.2).

| Feature | Notes |
|---------|-------|
| AES-256-GCM encryption at rest | Files on PC encrypted after save |
| PBKDF2 key derivation | Password-based, user sets it once |
| Encrypted manifest | `.lcloud/manifests/` also encrypted |

No timeline set. No code started.

---

### v0.5 — Open Source Release · Planned

Everything needed to publish publicly and hand off to users and contributors.

| Feature | Notes |
|---------|-------|
| Windows background service | Auto-start with Windows, runs without the main window |
| Full settings screen | Port, threshold %, backup folder, theme |
| Toast notifications | On backup complete and restore complete |
| GitHub public release | README, license, contributing guide |
| Android APK in GitHub Releases | Direct download without building |

No timeline set. No code started.

---

## Feature Backlog (Version Unassigned)

These are confirmed features — they will be built but haven't been assigned to a specific version yet.

| Feature | Why It Matters | Priority |
|---------|----------------|----------|
| Priority engine | WhatsApp first, then newest photos, then videos, then docs | High |
| Storage threshold trigger | Phone at <15% free → backup starts automatically | High |
| Duplicate detection (SHA-256) | Skip files already on PC — stop re-transferring on every backup | High |
| Resume interrupted backups | WiFi drop mid-transfer shouldn't mean restarting everything | Medium |
| "Delete after backup" | Remove backed-up files from phone to free space | Medium |
| Backup history persistence | History survives app restarts (currently in-memory only) | Medium |
| Transfer speed + ETA | Show MB/s and time remaining during backup | Low |
| Open Folder button on PC | Open backup folder in Windows Explorer from inside the app | Low |

---

## Future (Post v0.5)

Ideas that are out of scope for the current release plan but worth revisiting.

| Idea | Blocker |
|------|---------|
| iOS support | iOS sandboxing prevents silent file reads; needs explicit share-sheet integration |
| Scheduled backups (time-based) | Background daemon needed on both sides |
| Selective backup (include/exclude folders) | UI complexity; wait until core features stable |
| Multiple PC targets | Architecture supports it but UI doesn't |
| NAS / network folder as destination | Path handling change; low demand until v0.5 user feedback |
| Background auto-backup on home WiFi | Needs WorkManager + persistent background service on Android |

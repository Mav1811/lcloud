# Lcloud — Feature Roadmap

## What Makes Lcloud Different

LocalSend, SyncThing, Droid Transfer — they all do file transfer.  
**Lcloud does automatic backup with intelligence.**

| Feature | Lcloud | LocalSend | SyncThing |
|---------|--------|-----------|-----------|
| Smart priority (WhatsApp first) | ✅ v0.2 | ❌ | ❌ |
| Auto-trigger at low storage | ✅ v0.2 | ❌ | ❌ |
| Organized folders (date/type) | ✅ v0.1 | ❌ | ❌ |
| No internet / no cloud | ✅ | ✅ | ✅ |
| Open source | ✅ | ✅ | ✅ |
| Android → Windows | ✅ | ✅ | ✅ |
| Encryption | v0.4 | ✅ | ✅ |
| iOS support | Future | ✅ | ✅ |

---

## Version Plan

### v0.1 — Prototype (CURRENT)
**Goal:** End-to-end working backup. Ugly is OK, broken is not.

| Feature | Status |
|---------|--------|
| PC tray icon + window | ✅ |
| Folder picker | ✅ |
| mDNS device discovery | ✅ |
| File transfer (HTTP over WiFi) | ✅ |
| File organization (type + date) | ✅ |
| Android app with Backup Now | ✅ |
| WhatsApp media support | ✅ |
| Setup scripts | ✅ |

---

### v0.2 — Smart Engine
**Goal:** The two core differentiators working.

| Feature | Priority |
|---------|---------|
| Priority engine (WhatsApp → Photos → Videos → Docs) | High |
| Storage threshold trigger (15% free → auto-backup) | High |
| "Delete after backup?" prompt | Medium |
| Progress bar with speed + ETA | Medium |
| Low storage warning on PC | Medium |

---

### v0.3 — Reliability
**Goal:** Users can trust it. No lost files, no infinite loops.

| Feature | Priority |
|---------|---------|
| Duplicate detection (SHA-256 hash) | High |
| Resume interrupted backups | High |
| Retry on connection failure | Medium |
| Backup history log | Medium |
| mDNS fallback: manual IP input | Medium |

---

### v0.4 — Security
**Goal:** Safe to use for real. People's photos deserve encryption.

| Feature | Priority |
|---------|---------|
| AES-256-GCM encryption at rest | High |
| Password protection (PBKDF2) | High |
| HTTPS/TLS for transfer | High |

---

### v0.5 — Open Source Release
**Goal:** Real users can install and use it.

| Feature | Priority |
|---------|---------|
| Windows auto-start (background service) | High |
| Settings screen (port, threshold, dark/light mode) | Medium |
| Toast notifications | Medium |
| Backup stats dashboard | Low |
| GitHub repo + README | High |
| Android APK release | High |
| Contributing guide | Medium |

---

## Future (Post v0.5)
- iOS support (Flutter makes this feasible)
- Selective backup (choose specific folders)
- Scheduled automatic backups (time-based, not just storage-based)
- PC → Phone restore
- Multiple PC targets
- NAS/network folder support

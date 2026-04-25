# Lcloud — Architecture & Technical Decisions

**All design choices, tradeoffs, and technical details. Updated as decisions change.**

---

## System Overview

```
Android (Flutter/Dart)               Windows PC (Python 3.12)
──────────────────────               ────────────────────────

LcloudDiscovery                      LcloudDiscovery
  └─ UDP multicast listen        ←    └─ broadcasts every 2s to 224.0.0.167:53317
  └─ parses JSON beacon               └─ {alias, fingerprint, port, protocol:"https"}

TransferClient                       BackupEngine (HTTPS server, port 53317)
  └─ verifies cert by SHA-256    →    └─ POST /prepare-upload
     fingerprint (TOFU)               └─ POST /upload  (streamed, 65536-byte chunks)
  └─ streams files via openRead()     └─ POST /cancel
  └─ GET /restore/* endpoints    ←    └─ GET  /restore/sessions
                                       └─ GET  /restore/files
                                       └─ GET  /restore/file

FileScanner                          FileOrganizer
  └─ scans phone storage              └─ sorts into Photos/Videos/WhatsApp/Docs/Other
  └─ WhatsApp, DCIM, Downloads        └─ sub-folders by year/month
  └─ category + modified date         └─ filename collision prevention

                                      RestoreHandler
                                       └─ reads manifests
                                       └─ issues one-time tokens
                                       └─ resolves tokens on file request
```

---

## Key Design Decisions

### 1. LocalSend transport (multicast UDP + HTTPS push) — NOT mDNS + HTTP pull

**Decision:** Copy LocalSend's proven transport architecture.

**Why:**
- mDNS (v0.1) relied on Bonjour/Zeroconf which Windows Firewall blocks by default. Discovery failed silently for most users.
- PC-pull model (v0.1) gave fake progress — the PC couldn't know which file was being served until after the fact.
- LocalSend is deployed to millions of devices and their protocol is battle-tested on home networks.

**Tradeoff:** Phone now pushes files (more complex Android side). Accepted — the real-progress and security benefits outweigh it.

---

### 2. Port 53317 for everything

**Decision:** Use port 53317 for both UDP multicast and HTTPS server.

**Why:** Same port as LocalSend, which is on the open ports list for most home routers and ISPs. Avoids firewall configuration for users.

**Tradeoff:** Port collision if user also runs LocalSend. Extremely unlikely at home; accepted.

---

### 3. Self-signed cert + SHA-256 fingerprint TOFU (no CA)

**Decision:** PC generates one RSA-2048 self-signed cert on first run. Android trusts it by fingerprint, not by CA chain.

**Why:**
- A CA-based model requires either a commercial cert (cost, annual renewal) or a self-hosted CA (too complex for target user).
- LocalSend uses the same TOFU model and it works seamlessly.
- The fingerprint is broadcast in every UDP packet. Android receives it before any HTTPS connection — the cert can't be spoofed by a MITM without controlling the UDP broadcast too.

**Tradeoff:** No revocation. If the cert leaks, attacker can MITM indefinitely (until cert is rotated). Acceptable for a local-network-only tool; target users are not high-value attack targets.

**Cert storage:** `%LOCALAPPDATA%\lcloud\lcloud.crt` and `lcloud.key` — not in the repo (gitignored).

---

### 4. Manifest for restore: per-session JSON, relative paths

**Decision:** After every completed backup, PC writes a JSON manifest at `{backup_root}/.lcloud/manifests/{session_id}.json` recording each file's `originalPath` and `backedUpPath` (relative to backup_root, POSIX slashes).

**Why:**
- Relative paths survive if the user moves their backup folder to a different drive.
- Per-session files avoid a single growing manifest that becomes a write-contention problem at scale.
- JSON is human-readable — users can inspect or fix manifests manually.

**Tradeoff:** Manifests accumulate on disk forever. No cleanup mechanism yet. Accepted for now; can add a "clear old sessions" button in settings.

---

### 5. One-time tokens for restore file downloads

**Decision:** `GET /restore/files` issues a UUID token per file. The token is consumed on first use by `GET /restore/file`. Second use returns 401.

**Why:** Prevents replay attacks and stale token reuse. If a user requests the file listing and then waits an hour, their tokens are still valid — but each one can only be used once.

**Tradeoff:** If the download fails mid-stream, the token is gone. User must re-request the file listing to get a new token. Accepted — listing is fast and this is a rare edge case.

---

### 6. Push model (phone → PC)

**Decision:** Phone initiates the connection, prepares a session, and streams files to the PC.

**Why:**
- Real per-file progress: the PC knows exactly which file is uploading because the phone tells it before each upload.
- Simpler phone side: the phone knows what it has and what to send. The PC doesn't need to discover phone storage.
- Lower firewall friction: phone connects outbound to PC's HTTPS server. Most home firewalls allow outbound. Inbound connections (PC pulling from phone) are more often blocked.

---

### 7. Python + CustomTkinter for the PC app

**Decision:** Python 3.12 for all PC-side logic. CustomTkinter for the UI.

**Why:**
- Python is the fastest path from idea to working code for a solo developer.
- CustomTkinter provides a modern-looking UI on Windows without needing Electron or a full web stack.
- Packaging via PyInstaller gives a single `.exe` that doesn't require Python installation.

**Tradeoff:** Python startup time (~1.5s). CustomTkinter is not native Windows — looks slightly off from native apps. Acceptable for a free, open-source tool.

---

### 8. Flutter/Dart for the Android app

**Decision:** Flutter for the Android side.

**Why:**
- Single codebase for potential iOS support later (rewrite-free).
- Flutter's widget system produces consistent UI across Android versions.
- Dart's async/await model handles streaming file uploads cleanly.

**Tradeoff:** Flutter adds ~20MB to the APK. Fine for a backup app (not a widget or utility where size matters).

---

### 9. No account, no server, no internet — ever

**Decision:** Lcloud never connects to any server outside the user's LAN.

**Why:** Core trust signal. The target user segment is switching away from cloud services because they don't trust them. Adding any cloud component — even for telemetry — would undermine the product's value proposition.

**Tradeoff:** No remote support, no crash reporting, no usage analytics. Debug information comes from local log files only.

---

## Protocol Details

### Discovery (UDP Multicast)

PC broadcasts every 2 seconds to `224.0.0.167:53317`:

```json
{
  "alias": "MyPC",
  "version": "1.0",
  "deviceType": "desktop",
  "protocol": "https",
  "port": 53317,
  "fingerprint": "ab12cd34ef..."
}
```

Android listens on the multicast group. On first valid beacon, it records the PC's address and fingerprint, then stops listening and starts the backup UI.

**Android requires a multicast lock:** The platform channel `com.lcloud.lcloud/multicast` acquires `WifiManager.MulticastLock` to prevent the Android WiFi driver from filtering multicast packets.

---

### Backup Protocol (HTTPS)

**Step 1 — Prepare:**
```
POST /api/lcloud/v2/prepare-upload
{
  "deviceAlias": "Pixel 7",
  "files": [{ "fileId", "fileName", "size", "fileType", "path", "category", "modifiedAt" }]
}
→ { "sessionId": "uuid", "files": { "fileId": "token" } }
```

**Step 2 — Upload (one per file):**
```
POST /api/lcloud/v2/upload?sessionId=X&fileId=Y&token=Z
Content-Type: application/octet-stream
Content-Length: N
[raw bytes, streamed in 65536-byte chunks]
→ { "success": true }
```

**Step 3 — Cancel (on error or user cancel):**
```
POST /api/lcloud/v2/cancel?sessionId=X
→ { "cancelled": true }
```

---

### Restore Protocol (HTTPS GET)

**List sessions:**
```
GET /api/lcloud/v2/restore/sessions
→ { "sessions": [{ "sessionId", "startedAt", "completedAt", "deviceAlias", "fileCount", "totalBytes" }] }
```

**List files (with tokens):**
```
GET /api/lcloud/v2/restore/files?sessionId=X[&category=photo|video|whatsapp|document|other]
→ { "sessionId", "files": [...], "tokens": { "fileId": "one-time-token" } }
```

**Download one file (token consumed on use):**
```
GET /api/lcloud/v2/restore/file?sessionId=X&fileId=Y&token=Z
→ [raw bytes, streamed]
```

---

### Manifest Format

Written by PC at `{backup_root}/.lcloud/manifests/{session_id}.json`:

```json
{
  "sessionId": "550e8400-e29b-41d4-a716-446655440000",
  "startedAt": "2026-04-20T10:30:00",
  "completedAt": "2026-04-20T10:45:00",
  "deviceAlias": "Pixel 7",
  "files": [
    {
      "fileId": "a1b2c3d4",
      "fileName": "photo_001.jpg",
      "originalPath": "/storage/emulated/0/DCIM/Camera/photo_001.jpg",
      "backedUpPath": "Photos/2026/04/photo_001.jpg",
      "category": "photo",
      "sizeBytes": 3145728,
      "modifiedAt": "2026-04-19T14:22:00"
    }
  ]
}
```

`backedUpPath` is always relative to `backup_root` and uses POSIX forward slashes.

---

## File Organization

FileOrganizer sorts backed-up files into this structure:

```
{backup_root}/
├── Photos/
│   └── {year}/
│       └── {month}/       ← e.g. Photos/2026/04/photo.jpg
├── Videos/
│   └── {year}/{month}/
├── WhatsApp/
│   ├── Images/
│   ├── Video/
│   ├── Audio/
│   └── Documents/
├── Documents/
│   └── {year}/{month}/
└── Other/
    └── {year}/{month}/
```

Category is detected by file extension. WhatsApp files are detected by path prefix (`/WhatsApp/` in the original phone path).

Filename collisions are resolved by appending `_1`, `_2`, etc.

---

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Android app | Flutter / Dart | Flutter 3.41.6 |
| PC app | Python | 3.12 |
| PC UI | CustomTkinter | Latest |
| PC binary | PyInstaller | Latest |
| TLS cert | cryptography (Python) | ≥ 42.0.0 |
| Android HTTP | dart:io HttpClient | Built-in |
| Android crypto | crypto package | pubspec.yaml |
| Android intl | intl package | pubspec.yaml |
| Discovery | UDP multicast | No library — raw sockets |

---

## Build Environment

| Tool | Location |
|------|----------|
| Flutter 3.41.6 | `H:\fun\tools\flutter\bin` |
| JDK 17 (Microsoft) | `H:\fun\tools\jdk-17.0.18+8` |
| Android SDK | `C:\Users\{user}\AppData\Local\Android\Sdk` |
| Python 3.12 | System PATH |

---

## Known Limitations

| Limitation | Severity | Notes |
|-----------|----------|-------|
| No duplicate detection | High | Every backup re-transfers all files. Will cause churn. Fix: SHA-256 hash check before upload. |
| No transfer resume | Medium | WiFi drop = restart from zero. Fix: session-based checkpointing. |
| Single restore token use | Low | Download failure burns the token. User must re-request listing. |
| Manifests accumulate | Low | No cleanup. Future: "clear sessions older than X days" in settings. |
| No cert revocation | Low | Acceptable for local-network-only tool. |
| Port 53317 conflict with LocalSend | Very Low | If user runs both simultaneously. |

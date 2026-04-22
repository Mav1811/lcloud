# LocalSend-Inspired Transport Layer — Design Spec
**Date:** 2026-04-22  
**Project:** Lcloud v0.2  
**Status:** Approved

---

## Problem

Lcloud v0.1 transport has structural bugs:
- mDNS discovery requires Bonjour/Zeroconf, unreliable on Windows
- PC pulls files from phone's HTTP server — fake progress, no real per-file tracking
- No encryption (plain HTTP)
- No timeout — backup loop can hang forever
- Discovery runs once and gives up

## Solution

Adopt LocalSend's proven architecture: multicast UDP discovery + HTTPS push model + self-signed certificates. Keep all Lcloud-specific features (smart priority, file organizer, storage threshold).

---

## Architecture

```
Phone                               PC
─────                               ──────────────────────────
Multicast UDP listener         ←    Broadcasts every 2s on 224.0.0.167:53317
                                    {alias, fingerprint, port, protocol}

FileScanner (priority order)
  POST /prepare-upload          →   HTTPS server on port 53317
  ← {sessionId, fileTokens}    ←   Validates space, returns session

  POST /upload?session&file&token → Saves via FileOrganizer → progress callback
  POST /upload (next file)      →   Real per-file progress
  ...
  POST /cancel (on error/cancel)→   Cleanup temp files
```

---

## Security Model

- PC generates one self-signed RSA-2048 certificate on first run
- Stored at `%LOCALAPPDATA%\lcloud\lcloud.crt` + `lcloud.key`
- Fingerprint = SHA-256 of DER-encoded cert bytes
- Fingerprint included in every UDP broadcast
- Android trusts the cert by fingerprint (Trust On First Use)
- No CA verification — same model as LocalSend

---

## Discovery Protocol

**PC → multicast every 2 seconds:**
```json
{
  "alias": "MyPC",
  "version": "1.0",
  "deviceType": "desktop",
  "fingerprint": "<sha256-hex>",
  "port": 53317,
  "protocol": "https"
}
```

**Android:**
- Joins multicast group on startup
- Parses first valid PC broadcast
- Caches IP + fingerprint
- Auto-reconnects if PC disappears (retries every 10s)

---

## Transfer Protocol

**Base URL:** `https://<pc-ip>:53317/api/lcloud/v2/`

### GET /info
Returns PC identity. Used for fingerprint verification before first transfer.

**Response:**
```json
{"alias": "MyPC", "fingerprint": "<sha256>", "deviceType": "desktop"}
```

---

### POST /prepare-upload
Phone sends file list. PC validates disk space and returns tokens.

**Request:**
```json
{
  "deviceAlias": "MyPhone",
  "files": [
    {
      "fileId": "uuid",
      "fileName": "IMG_001.jpg",
      "size": 3145728,
      "fileType": "image/jpeg",
      "path": "/storage/emulated/0/DCIM/IMG_001.jpg",
      "category": "photo",
      "modifiedAt": "2026-04-20T10:30:00"
    }
  ]
}
```

**Responses:**
- `200` → `{"sessionId": "uuid", "files": {"fileId": "token", ...}}`
- `503` → `{"error": "no_backup_folder"}` — PC has no folder set
- `507` → `{"error": "insufficient_storage", "free_bytes": N, "needed_bytes": N}`

---

### POST /upload?sessionId=X&fileId=Y&token=Z
Phone streams raw file bytes. PC saves to temp → organizes via FileOrganizer → emits progress.

**Response:**
- `200` → `{"success": true}`
- `401` → `{"error": "invalid_token"}` — bad session or token
- `500` → `{"error": "write_failed", "detail": "..."}`

---

### POST /cancel?sessionId=X
Abort session. PC deletes any temp files for this session.

**Response:** `{"cancelled": true}`

---

## Progress (Real, Per-File)

**PC side:** After each `/upload` completes, fires callback:
```
on_progress(filename, index, total, bytes_done, bytes_total, speed_mbps)
```

**Android side:** Tracks real bytes sent via `StreamedRequest` — shows live progress bar with speed + ETA.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| PC not found after 30s | Show "Can't find PC" with retry button |
| WiFi drops mid-transfer | Socket timeout (60s/file) → cancel session → show error |
| Disk full | 507 → phone shows warning with free/needed MB |
| No backup folder on PC | 503 → phone shows "Open Lcloud on PC and set a folder" |
| Bad token | 401 → phone cancels and shows error |
| File write failure | 500 → skip file, continue, report errors at end |

---

## Components Changed

### PC (Python) — `lcloud-pc/src/`

| File | Change |
|------|--------|
| `core/certs.py` | **NEW** — generate/load/store self-signed cert |
| `core/discovery.py` | **REWRITE** — multicast UDP broadcaster (drop zeroconf) |
| `core/backup_engine.py` | **REWRITE** — HTTPS server, new endpoints, real progress |
| `config.py` | **UPDATE** — port 53317, cert paths, multicast address |

### Android (Dart) — `lcloud-android/lib/`

| File | Change |
|------|--------|
| `services/discovery.dart` | **REWRITE** — multicast UDP listener (drop mDNS) |
| `services/transfer_client.dart` | **NEW** — HTTPS push client with streaming progress |
| `services/http_server.dart` | **REMOVE** — no longer needed |
| `screens/home_screen.dart` | **UPDATE** — new backup flow wired to transfer_client |

---

## Testing Plan

### PC Unit Tests
- `test_certs.py` — cert generation, fingerprint derivation, reload
- `test_backup_engine.py` — session creation, token validation, file write, cancel, disk full, no folder

### PC Integration Test
- Start HTTPS server, simulate full prepare→upload→complete flow via requests

### Android Widget Tests
- HomeScreen states: searching → found → backing up → complete → error

### Manual End-to-End
- Real phone on real WiFi → full backup → verify files organized correctly

---

## What Stays the Same

- `FileScanner` — smart priority ordering (WhatsApp → Photos → Videos → Docs)
- `FileOrganizer` — folder structure by type + date
- All UI (PC window, tray, Android home screen layout)
- Settings persistence (port changes to 53317 default)
- Backup history

---

## Port Change

| | Old | New |
|-|-----|-----|
| PC listen port | 52000 | 53317 |
| Phone server port | 52001 | removed |
| Protocol | HTTP | HTTPS |
| Discovery | mDNS | Multicast UDP 224.0.0.167:53317 |

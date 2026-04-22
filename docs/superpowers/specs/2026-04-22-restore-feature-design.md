# Restore Feature — Design Spec
**Date:** 2026-04-22
**Project:** Lcloud v0.3
**Status:** Approved

---

## Problem

Lcloud backs up files from Android → PC but has no way to get them back.
Users need to restore specific files to their phone — to the exact original location — without manually digging through the backup folder on their PC.

---

## Goals

- Browse all backed-up files by session and by category
- Select individual files, whole sessions, or filtered subsets to restore
- Files land in their original location on the phone (seamless — user finds them where they left them)
- Skip files that already exist — no overwrites, no prompts
- If original folder is missing, ask once per folder: create it or use `Lcloud_Restored/`
- A failure on one file never stops the rest

---

## Approach

**Manifest + HTTPS pull.**

During every backup the PC writes a `manifest.json` recording each file's original phone path alongside its backed-up location. For restore, the Android app reads the manifest via the existing HTTPS server, the user picks files, and the phone pulls them back one by one — writing each to its recorded original path.

No new transport protocol. Uses the same HTTPS server, same fingerprint trust, same streaming pattern already built for backup.

---

## Manifest

Written by the PC at the end of every backup session.

**Location:** `{backup_root}/.lcloud/manifests/{session_id}.json`

**Format:**

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

**Key fields:**
- `originalPath` — absolute path on phone where the file lived before backup. Used to restore to the exact original location.
- `backedUpPath` — path **relative to `backup_root`**. PC resolves the actual file at `{backup_root}/{backedUpPath}`. Relative so the manifest stays valid if the user moves their backup folder.
- `fileId` — same ID used during the upload session. Used to request tokens for restore.

**Written when:** after all files in a session are uploaded. If a session is cancelled or fails, no manifest is written (partial sessions are not restorable).

---

## Protocol — New PC Endpoints

All endpoints are on the existing HTTPS server (port 53317). Same TLS cert, same fingerprint verification.

### GET /api/lcloud/v2/restore/sessions

Returns all available backup sessions, newest first.

**Response:**
```json
{
  "sessions": [
    {
      "sessionId": "uuid",
      "startedAt": "2026-04-20T10:30:00",
      "completedAt": "2026-04-20T10:45:00",
      "deviceAlias": "Pixel 7",
      "fileCount": 823,
      "totalBytes": 1547600000
    }
  ]
}
```

**Errors:**
- `404` if manifest directory doesn't exist yet (no backups ever run)

---

### GET /api/lcloud/v2/restore/files?sessionId=X&category=photo

Returns all files in a session, optionally filtered by category.

`category` values: `photo`, `video`, `whatsapp`, `document`, `other`. Omit to return all.

**Response:**
```json
{
  "sessionId": "uuid",
  "files": [
    {
      "fileId": "a1b2c3d4",
      "fileName": "photo_001.jpg",
      "originalPath": "/storage/emulated/0/DCIM/Camera/photo_001.jpg",
      "category": "photo",
      "sizeBytes": 3145728,
      "modifiedAt": "2026-04-19T14:22:00",
      "available": true
    }
  ],
  "tokens": {
    "a1b2c3d4": "restore-token-uuid"
  }
}
```

`available: false` means the backed-up file is missing from PC disk — the Android app shows it greyed out and non-selectable.

`tokens` — one-time restore tokens, one per file. Used to authorise the download endpoint.

**Errors:**
- `404` if session not found

---

### GET /api/lcloud/v2/restore/file?sessionId=X&fileId=Y&token=Z

Streams the backed-up file bytes from PC disk to the phone.

**Response:** raw file bytes, `Content-Type` set from file extension, `Content-Length` set.

**Errors:**
- `401` — invalid or expired token
- `404` — file not found on disk
- `500` — read error

---

## Android — New Components

### `lib/services/restore_client.dart`

HTTPS client for the three restore endpoints. Same fingerprint verification as `TransferClient`. Methods:
- `getSessions()` → `List<RestoreSession>`
- `getFiles(sessionId, {category})` → `RestoreFileListing` (files + tokens)
- `downloadFile(sessionId, fileId, token, destPath, {onProgress})` → streams file to `destPath`

### `lib/screens/restore_screen.dart`

Full restore UI. Single screen with:
- Category filter tabs: All / Photos / Videos / WhatsApp / Documents
- Expandable session rows (tap to expand, tap again to collapse)
- File rows within each session: icon, name, size, checkbox
- "Select All" in session header selects all visible (filtered) files in that session
- "Restore X files" button fixed at bottom — disabled when nothing selected
- Progress view (reuses existing `ProgressCard` widget) replaces file list during restore
- End-of-restore summary: X restored, Y skipped, Z failed

### `lib/screens/home_screen.dart` (modified)

Adds a "Restore" outlined button below the existing "Backup Now" button. Navigates to `RestoreScreen`.

---

## Restore Flow (Android)

```
1. User opens RestoreScreen
2. App calls GET /restore/sessions → shows session list
3. User expands a session, applies category filter, selects files
4. User taps "Restore X files"
5. App calls GET /restore/files (again, to get fresh tokens)
6. For each selected file:
   a. Check if file already exists at originalPath → SKIP if yes
   b. Check if parent folder exists:
        - If missing → show one prompt per unique missing folder
            → User picks: Create folder  OR  Use Lcloud_Restored/
        - If user picks Create: mkdir -p originalPath's parent
        - If user picks Lcloud_Restored/: change destPath to
            /storage/emulated/0/Lcloud_Restored/{category}/{fileName}
   c. Check phone free space (total for all remaining files) → warn if insufficient
   d. Call GET /restore/file → stream to resolved destPath
   e. Update progress bar
7. Show summary: X restored · Y skipped · Z failed
   - Failed files listed by name with "Retry failed" button
```

**Missing folder prompt fires once per unique parent folder, not once per file.**
If 50 WhatsApp images share the same missing folder, one dialog covers all 50.
The user's choice (create / fallback) is remembered for that folder for the duration of the restore session.

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| PC not connected | "Connect to PC first" with refresh — same as backup screen |
| No sessions found | Empty state: "No backups yet. Run a backup first." |
| Manifest corrupt / unreadable | Skip that session, show rest |
| File `available: false` | Greyed out in list, not selectable, tooltip: "File not found on PC" |
| File already exists at original path | Skip silently — no prompt |
| Original folder missing | One prompt per folder: Create it OR use `Lcloud_Restored/` |
| Phone storage full | Pre-check before starting → show warning with MB needed vs MB free |
| WiFi drops mid-file | 60s timeout → mark file as failed, continue with next |
| One file fails | Log it, continue all other files — never abort the whole restore |
| All files fail | Show full error list with "Retry failed" button |

---

## Components Changed / Created

### PC (`lcloud-pc/src/`)

| File | Change |
|------|--------|
| `core/backup_engine.py` | Write manifest after each session completes |
| `core/restore_handler.py` | **NEW** — reads manifests, serves restore endpoints |
| `config.py` | Add `MANIFEST_DIR` constant |

### Android (`lcloud-android/lib/`)

| File | Change |
|------|--------|
| `services/restore_client.dart` | **NEW** — HTTPS client for restore endpoints |
| `models/restore_session.dart` | **NEW** — data classes: RestoreSession, RestoreFile |
| `screens/restore_screen.dart` | **NEW** — full restore UI |
| `screens/home_screen.dart` | Add Restore button → navigate to RestoreScreen |

---

## What Is NOT in This Release

- Restoring to a different phone than the one that backed up (future)
- Scheduling automatic restores (future)
- Restoring to a PC folder from Android (future)
- Encrypting manifests (follows v0.4 encryption work)

---

## Version Target

**v0.3** — alongside duplicate detection and resume (already planned in ROADMAP.md).
Restore is the third differentiator that makes Lcloud genuinely useful as a backup tool, not just a file transfer tool.

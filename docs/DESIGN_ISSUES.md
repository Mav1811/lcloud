# Lcloud v0.1 — Design Issues

Critical review of known problems before v0.2 work begins.
Issues are grouped by severity.

---

## Critical (fix before real users touch it)

### 1. No duplicate detection — every backup re-transfers everything
Both sides have no way to know if a file was already backed up.
If you have 2GB of photos, every single backup costs 2GB of transfer.
This will make users uninstall it on the second backup.
**Fix in:** v0.2 or v0.3 (SHA-256 hash check before transfer)

### 2. "Delete from Phone" button does nothing
After backup completes, a dialog asks "do you want to delete backed-up files?"
Tapping "Delete from Phone" just shows a toast: "coming in v0.3."
You promised the user an action and then did nothing. Confusing and untrustworthy.
**Fix in:** v0.2 — either implement it or remove the button entirely until it works

### 3. Discovery runs once and gives up
If the PC isn't running when you open the app, it searches once, fails, and shows
"Searching for phone on WiFi…" forever with no retry.
User has no idea if it's still trying or permanently stuck.
**Fix in:** v0.2 — add a retry loop (e.g. retry every 10 seconds)

### 4. Files found count never resets after backup
The stats row ("X files found") shows the same files every time — including files
already backed up. Since there's no duplicate detection, it always looks like
everything needs to be backed up again.
**Fix in:** depends on #1 — once hashes exist, filter already-backed-up files

### 5. No cancel button during backup
Once backup starts, there is no way to stop it.
The "Backup Now" button just says "Backing up…" and the user is locked out.
**Fix in:** v0.2

---

## Functional Problems

### 6. Fake progress tracking
The progress bar estimates which file is transferring by dividing bytes served
proportionally across all files. It is not real per-file tracking.
File names shown during transfer can be wrong, and the counter can jump or stall.
**Fix in:** v0.2 — PC should emit per-file callbacks as it completes each download

### 7. No timeout on the backup loop (Android)
If WiFi drops mid-transfer, the while loop on the Android side keeps running,
waiting for bytesServed to reach totalBytes. It will loop forever.
**Fix in:** v0.2 — add a timeout (e.g. 30 seconds of no new bytes = fail)

### 8. History lost on every app restart (both sides)
Backup history is stored in memory only. Close either app and all history is gone.
The history panel is useless across sessions.
**Fix in:** v0.2 — persist to SharedPreferences (Android) and settings.json (PC)

### 9. "Backup Now" button on PC makes no sense
The PC is the receiver — the phone initiates backup. A "Backup Now" button on
the PC is confusing. It's unclear what it does or who it's for.
**Fix in:** v0.2 — remove it, or repurpose it as "trigger backup on connected phone"

---

## Polish / UX Issues

### 10. No "Open Folder" button on PC
After files are backed up, there's no way to open the backup folder from inside the app.
User has to find it manually in Windows Explorer.
**Fix in:** v0.2 — add an "Open Folder" link/button next to the folder path

### 11. No transfer speed or ETA in progress
Progress shows file count and MB transferred but no speed (MB/s) and no time estimate.
You can't tell if the transfer is going fast or silently stalled.
**Fix in:** v0.2 — track bytes/sec and show estimated time remaining

### 12. IP address shown in Android status card
"IP: 192.168.1.105" is meaningless to a normal user.
It's raw technical info sitting on the main screen.
**Fix in:** v0.2 — hide it or move it to a "details" tap

### 13. Settings on PC only has one option
The settings dialog exists (gear button) but only lets you change the port number.
Everything else (threshold %, folder, auto-start) is missing.
**Fix in:** v0.5 — low priority, but the near-empty settings screen looks unfinished

---

## Summary Table

| # | Issue | Severity | Target |
|---|-------|----------|--------|
| 1 | No duplicate detection | Critical | v0.3 |
| 2 | Delete button does nothing | Critical | v0.2 |
| 3 | Discovery doesn't retry | Critical | v0.2 |
| 4 | File count never resets | Critical | v0.3 |
| 5 | No cancel during backup | Critical | v0.2 |
| 6 | Fake progress tracking | Functional | v0.2 |
| 7 | No timeout on backup loop | Functional | v0.2 |
| 8 | History lost on restart | Functional | v0.2 |
| 9 | Backup Now on PC confusing | Functional | v0.2 |
| 10 | No Open Folder button | Polish | v0.2 |
| 11 | No speed / ETA in progress | Polish | v0.2 |
| 12 | IP shown in status card | Polish | v0.2 |
| 13 | Settings nearly empty | Polish | v0.5 |

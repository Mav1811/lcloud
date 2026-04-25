# Lcloud — Feature Brainstorming & Product Backlog

**Why this app exists, who it's for, what competitors miss, and what we're building next.**

---

## Why This App Exists

The demand for local, private, automatic Android-to-PC backup is consistently surfacing across Reddit, XDA, developer forums, and GitHub issue trackers. The same request — *"auto-backup my Android phone to my PC over WiFi for free with no account"* — appears year after year with no clean free answer.

The closest competitor (LocalSend, 78,600+ GitHub stars) deliberately refuses to add auto-backup. The second-closest (PhotoSync) charges for automatic sync and has a complex UI that alienates non-technical users. Cloud solutions (Google Photos, OneDrive) are pushing more users away with storage limits and privacy concerns.

**Lcloud's window:** automatic, no-account, WiFi-only backup with smart priority and storage trigger — a specific gap no major free open-source app fills.

---

## Who It's For

Three user segments, all underserved:

**Segment A — The Storage-Full User (52% of audience)**
Hit the Google Photos 15GB limit. Not politically motivated — just doesn't want to pay. Wants photos "somewhere safe, for free."
- Lcloud appeal: free, automatic, no account, just works

**Segment B — The WhatsApp-Heavy User (30% of audience)**
Primarily Android users in India, Southeast Asia, Latin America. WhatsApp media is their most important data.
- Lcloud appeal: WhatsApp backed up first, works on home WiFi, completely free

**Segment C — The Privacy-First User (18% of audience)**
Actively moving away from Google Photos. Cares about data sovereignty.
- Lcloud appeal: open source, no server required, stays local

**The largest segment (A) is the most underserved.** They don't have the technical ability to run Immich, don't want to pay for PhotoSync, and find LocalSend confusing because it's not automatic.

---

## Competitor Analysis

| Feature | Lcloud | LocalSend | PhotoSync | Immich | AirDroid |
|---------|--------|-----------|-----------|--------|----------|
| Auto-backup on home WiFi | ✅ Backlog | ❌ Refused | ✅ Paid only | ✅ | ✅ |
| No account required | ✅ | ✅ | ❌ | ✅ | ❌ |
| Storage threshold trigger | ✅ Backlog | ❌ | ❌ | ❌ | ❌ |
| Smart priority (WhatsApp first) | ✅ Backlog | ❌ | ❌ | ❌ | ❌ |
| File restore to original location | ✅ v0.3 | ❌ | Partial | Partial | ❌ |
| Secure HTTPS transfer | ✅ v0.2 | ✅ | ✅ | ✅ | ❌ |
| File organization (date/type) | ✅ v0.1 | ❌ | ✅ | ✅ | ❌ |
| Duplicate detection | ✅ Backlog | ❌ | ✅ | ✅ | ✅ |
| Free forever | ✅ | ✅ | ❌ | ✅ | ❌ |
| Open source | ✅ v0.5 | ✅ | ❌ | ✅ | ❌ |
| Works without internet | ✅ | ✅ | ✅ | ✅ | ❌ |

**Why each competitor loses:**
- **LocalSend:** A file *sender*, not a backup system. Deliberately manual. No auto-backup, no scheduling, no smart filtering. Background transfers fail on Android.
- **PhotoSync:** Auto-sync requires paid upgrade. Android version significantly worse than iOS. UI is overwhelming for non-technical users. Not open source.
- **AirDroid:** Requires account, uses cloud relay. Privacy-conscious users avoid it. Bloatware.
- **Immich:** Requires Docker, a server, Linux knowledge. Built for the top 5% of technical users. Lcloud targets the other 95%.
- **SyncMyDroid:** Near-abandoned. No community, no trust signal.

---

## The Two Killer Features (Not Built Yet)

These are what make Lcloud meaningfully different from every competitor. They're in the backlog but should be prioritized above everything else after v0.5.

### 1. Priority Engine
Back up files in an order that matters to the user — not random:

```
1. WhatsApp Media      (most irreplaceable — if phone is lost, WhatsApp is gone)
2. Photos (newest →)  (most recent are most likely not yet cloud-backed)
3. Videos             (large, slow to transfer — do last)
4. Documents
5. Other
```

If backup is interrupted at 30%, the user still got their most important files.

### 2. Storage Threshold Trigger
Android monitors free storage continuously. When it drops below 15% (configurable):
- Backup starts automatically in the background
- User gets a notification when done
- No app-opening required

This is the "set it and forget it" promise. No competitor has it for free.

---

## Current Known Issues

Issues identified in the existing builds, tracked for future fixes.

### Critical
| # | Issue | Status | Target |
|---|-------|--------|--------|
| 1 | No duplicate detection — every backup re-transfers everything | Open | Backlog |
| 2 | Files found count never resets after backup | Open | Depends on #1 |
| 3 | "Delete after backup" button does nothing (stub only) | Open | Backlog |

*Issues #3 from v0.1 (Discovery doesn't retry, no cancel button) were fixed in v0.2.*

### Functional
| # | Issue | Status | Target |
|---|-------|--------|--------|
| 4 | Backup history lost on every app restart (in-memory only) | Open | Backlog |
| 5 | No transfer resume on WiFi drop | Open | Backlog |

### Polish
| # | Issue | Status | Target |
|---|-------|--------|--------|
| 6 | No transfer speed or ETA shown during backup | Open | Backlog |
| 7 | No "Open Folder" button on PC after backup completes | Open | Backlog |
| 8 | Settings screen on PC nearly empty | Open | v0.5 |

---

## Prioritized Feature Backlog

In rough build order — what to tackle after v0.5 open source release.

**Tier 1 — Core experience (should ship before considering v1.0)**

1. **Duplicate detection (SHA-256)** — Skip files already on PC. Without this, every backup re-transfers everything. Users will churn.
2. **Priority engine** — WhatsApp first, newest photos next. Interrupted backups save what matters most.
3. **Storage threshold trigger** — Auto-backup when phone is nearly full. The "set and forget" promise.
4. **Backup history persistence** — History should survive app restarts (SharedPreferences on Android, JSON on PC).

**Tier 2 — Reliability**

5. **Resume interrupted backups** — WiFi drop mid-transfer shouldn't require restarting from zero.
6. **"Delete after backup"** — Actually remove backed-up files from phone to free space.
7. **Transfer speed + ETA** — Show MB/s and time remaining. Currently shows bytes transferred with no rate.

**Tier 3 — Polish**

8. **Open Folder button on PC** — Open backup folder in Explorer from inside the app.
9. **Full settings screen** — Threshold %, port, auto-start toggle, theme. Currently nearly empty.
10. **Toast notifications** — Windows notification when backup or restore completes.

---

## Future Ideas (Post v0.5, No Commitment)

Ideas worth tracking but not prioritized:

- **Background auto-backup on home WiFi** — Detect home WiFi SSID, start backup automatically on connect
- **iOS support** — Flutter makes it feasible, but iOS sandbox prevents silent file access
- **Scheduled backups** — Nightly at 2am, etc. Needs background daemon
- **Selective backup** — Exclude specific folders (e.g., Screenshots, Downloads)
- **Multiple PC targets** — Back up to two PCs (home + office)
- **NAS / network folder** — Destination doesn't have to be local disk
- **Web UI on PC** — Browse backup from any browser on the network

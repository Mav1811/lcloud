# App Features Comparison — Lcloud vs Competitors
**Date:** April 2026  
**Purpose:** Side-by-side feature breakdown to identify what Lcloud must have, should have, and can skip

---

## Quick Reference Table

| Feature | Lcloud | LocalSend | PhotoSync | SyncMyDroid | AirDroid | Immich |
|---------|--------|-----------|-----------|-------------|----------|--------|
| Auto-backup on home WiFi | ✅ Planned | ❌ | ✅ Paid only | ✅ | ✅ | ✅ |
| Manual backup (on-demand) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Backup to Windows PC | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ (server) |
| No internet / no cloud | ✅ | ✅ | ✅ | ✅ | ❌ (cloud relay) | ✅ |
| Storage threshold trigger | ✅ Planned | ❌ | ❌ | ❌ | ❌ | ❌ |
| Smart priority (WhatsApp first) | ✅ Planned | ❌ | ❌ | ❌ | ❌ | ❌ |
| No account required | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| Open source | ✅ (v0.5) | ✅ | ❌ | ❌ | ❌ | ✅ |
| End-to-end encryption | ✅ v0.4 | ✅ | ❌ | ❌ | ❌ | ❌ |
| Resume interrupted transfer | ✅ v0.3 | ❌ | ❌ | ❌ | ✅ | ✅ |
| Duplicate detection | ✅ v0.3 | ❌ | ✅ | ✅ | ✅ | ✅ |
| Auto-organise into folders | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ |
| Free forever | ✅ | ✅ | ❌ (paid auto) | ❌ | ❌ (freemium) | ✅ |

---

## LocalSend — Closest Competitor

**What it is:** Free, open-source file *sender* (not a backup tool) for local WiFi transfer across all platforms.  
**GitHub Stars:** 78,600+ | **Open Issues:** 884

**Has:**
- Dead-simple device discovery (mDNS)
- Truly open source (MIT)
- Works on all platforms (Windows, Mac, Linux, Android, iOS)
- End-to-end encryption (TLS)

**Critical gaps:**
- **No auto-backup.** Must open app and manually select files every time.
- **No scheduling.** Cannot run a transfer at a set time or when connecting to home WiFi.
- **No smart filtering.** Mass photo selection requires tapping each photo individually.
- **No storage threshold trigger.**
- **Background transfers fail.** Android suspends the app mid-transfer (confirmed bug December 2024).
- **No resume.** GitHub Issue #1191 (2024) — still unimplemented.

**Why users still need Lcloud:** It is a file *sender*, not a backup *system*. Deliberately manual.

---

## PhotoSync — Premium Paid Option

**Rating:** 4.36/5 (19,000+ ratings on iOS)

**Has:** Auto-sync (paid), duplicate detection, date-based folders, filter by type/date

**Gaps:**
- Auto-sync is a **paid upgrade**
- Android version significantly worse than iOS
- UI is complex and "overwhelming" for non-technical users
- Reliability issues: "stealth fail" with no error notification
- Not open source

---

## AirDroid — Over-Engineered

Requires account creation, uses cloud relay, becomes bloatware. Privacy-conscious users avoid it.

---

## Immich — Powerful But Unapproachable

Requires Docker, a server, Linux knowledge or a NAS.  
**Lcloud's advantage:** Immich is for the top 5% of technically capable users. Lcloud targets the other 95%.

---

## SyncMyDroid — Abandoned

Technically does what Lcloud plans, but near-abandoned. No community, no trust signal.

---

## Summary: What Lcloud Must Get Right

1. **Reliable auto-backup in the background** — the #1 ask across all forums, and the #1 thing LocalSend refuses to build
2. **Works for non-technical users** — PhotoSync and Immich both fail here; AirDroid requires an account  
3. **Free, forever** — PhotoSync's auto-backup is paid; AirDroid is freemium

The gaps (no iOS, no Mac, no date-range filter) are acceptable for v0.1 → v0.5. Target user is Android + Windows.

# Original Project Context
**Date:** April 2026  
**Purpose:** Historical record of the project's origin — initial specs, user's answers, and early blocker analysis. Kept for context but superseded by CLAUDE.md for active development guidance.

---

## How This Project Started

The user (Shangeeth) began by doing market research and AI-assisted planning before touching any code. The files below represent that initial planning phase.

---

## User's Original Requirements (Q&A)

*From the original setup Q&A — answers tell us who the user is and what they want.*

**Platform:** Windows PC + Android phone  
**Goal:** Open source the app eventually  
**Budget:** Free tools only  
**File types:** Everything, organized well  
**PC UI:** Minimal and aesthetic (not just a tray icon)  
**Android version:** Android 10+  
**Discovery:** Auto-discover phone — no manual IP typing  
**Encryption:** Later (not day one)  
**After backup:** Ask user whether to delete files from phone  
**Disk full:** Stop and warn on both PC and phone  
**App name:** Lcloud  
**WhatsApp:** Yes, include WhatsApp media files  
**Background service:** Yes, auto-start with Windows  

---

## Original Build Phases

*From the initial spec document — this was the initial plan before Claude Code took over.*

```
Phase 0   Fill gaps (answered in Q&A)
Phase 1   PC app skeleton: tray icon + empty window + folder picker
Phase 2   PC encryption: save/load files with AES-256
Phase 3   Android app: file scanner + HTTP server + sends files
Phase 4   PC receiver: discovers phone, downloads files, organizes them
Phase 5   Priority engine on Android side
Phase 6   Storage threshold trigger on Android
Phase 7   UI polish: progress bar, backup history, notifications
Phase 8   GitHub repo setup, README, open source release
```

*Note: This phasing was superseded. See ROADMAP.md for current version plan.*

---

## Early Blocker Analysis (Pre-Development Notes)

*From initial AI consultation — 4 blockers that could kill the project if ignored.*

**1. iOS is fundamentally different from Android.**  
iOS won't let any app silently read files in the background — the sandbox prevents it. The iOS version will have a narrower feature set by nature, not by choice. Plan for that from day one.

**2. You need a background daemon, not just an app.**  
An app window that needs to be open to trigger backups isn't "automatic." The PC side needs a native service (Windows Service) that runs silently. This is a separate engineering problem from the UI.

**3. No encryption = no credibility.**  
A backup tool that handles personal photos, WhatsApp media, and documents without encryption won't survive any real scrutiny. TLS in-transit and AES-256 at-rest are the baseline, not a v2 feature.  
*Status: TLS (HTTPS) is now in v0.2. AES-256 at rest planned for v0.4.*

**4. Decide your account architecture now.**  
"No account" is the decision — fully local, no backend. This shapes the entire architecture.  
*Status: Decided. No accounts, ever. Local only.*

---

## Competitive Advantage — Never Lose Sight

Nobody else has:
1. **Smart priority engine** — important stuff backed up first, not random order
2. **Storage threshold trigger** — phone tells PC "I'm almost full, help me"

These two features ARE the product. Everything else is infrastructure.

---

*See `market-analysis.md` and `competitor-comparison.md` for detailed research.*  
*See `CLAUDE.md` for current development state and active guidance.*

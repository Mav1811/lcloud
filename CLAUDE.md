# Lcloud — Claude Development Guide
> **How to resume work:** Read this file top to bottom first, then read the relevant spec/plan from `docs/superpowers/`. You will have full context within 3 minutes.

---

## Who Is Building This

**User:** Shangeeth (shangeeth2k@gmail.com) — non-technical user. He has an Android phone and a Windows PC. He wants an open-source WiFi backup app that he can eventually release publicly. He does not write code — Claude Code builds everything.

**Working style:**
- Give terse responses — user can read the diff
- Never add features or refactors beyond what was asked
- Superpowers skills are active: always invoke the relevant skill before acting
- TDD: write failing test first, then implement, then commit

---

## What Lcloud Is

Automatic WiFi backup from Android phone to Windows PC. No cloud, no internet, no account. Files stay local. Two killer features no competitor has:

1. **Smart priority engine** — WhatsApp first, then newest photos, then videos, then docs
2. **Storage threshold trigger** — phone hits 15% free → backup starts automatically

**Target user:** Android + Windows, non-technical, wants something that "just works for free."

---

## Current Version Status

| Version | Status | What it is |
|---------|--------|------------|
| v0.1 | ✅ Done | Working prototype — manual backup, file organization |
| v0.2 | ✅ Done | LocalSend-inspired transport (HTTPS push, cert trust, multicast discovery) |
| v0.3 | ✅ Done | Restore feature (manifests + 3 endpoints + RestoreScreen) |
| v0.4 | Planned | AES-256-GCM at-rest encryption |
| v0.5 | Planned | Open source release, Windows auto-start service |

**Important:** v0.2 is the transport rewrite, NOT the priority engine or storage trigger. Those are still unbuilt. The mDNS + HTTP pull architecture from v0.1 was broken and replaced with a proven LocalSend-inspired pattern.

---

## Architecture — CURRENT (v0.2 LocalSend-Inspired)

```
Android (Flutter/Dart)               Windows PC (Python 3.12)
──────────────────────               ────────────────────────
LcloudDiscovery                      LcloudDiscovery
  └─ UDP multicast listen        ←    └─ broadcasts every 2s to 224.0.0.167:53317
  └─ parses JSON beacon               └─ {alias, fingerprint, port, protocol:"https"}

TransferClient                       BackupEngine (HTTPS server, port 53317)
  └─ verifies cert by SHA-256    →    └─ GET  /api/lcloud/v2/info
     fingerprint (TOFU)               └─ POST /api/lcloud/v2/prepare-upload
  └─ POST prepare-upload              └─ POST /api/lcloud/v2/upload  (streamed)
  └─ streams files via openRead()     └─ POST /api/lcloud/v2/cancel
  └─ GET /restore/* endpoints    ←    └─ GET  /api/lcloud/v2/restore/sessions  (v0.3)
                                       └─ GET  /api/lcloud/v2/restore/files     (v0.3)
                                       └─ GET  /api/lcloud/v2/restore/file      (v0.3)
```

**Protocol:**
- Discovery: UDP multicast to `224.0.0.167:53317` every 2s
- Transfer: HTTPS on port `53317` (same port as LocalSend)
- TLS: self-signed RSA-2048 cert, SHA-256 fingerprint trust (TOFU)
- Streaming: phone pushes files in 65536-byte chunks via `File.openRead()`
- Android multicast requires a platform channel lock: `com.lcloud.lcloud/multicast`

---

## File Map (Complete)

```
lcloud/
├── CLAUDE.md                    ← THIS FILE — read first when resuming
├── README.md
├── ROADMAP.md
├── CHANGELOG.md
├── .gitignore
├── build-android.bat            ← builds lcloud-android.apk
├── build-pc.bat                 ← builds Lcloud.exe via PyInstaller
├── install-android.bat          ← installs APK to connected phone via adb
│
├── docs/
│   ├── USER_GUIDE.md
│   ├── DEV_GUIDE.md
│   ├── DESIGN_ISSUES.md         ← 13 known design issues with severity
│   ├── research/                ← market research and competitor analysis
│   │   ├── market-analysis.md
│   │   ├── competitor-comparison.md
│   │   └── original-project-context.md
│   ├── specs/
│   │   └── lcloud-design.md     ← original design spec (historical)
│   └── superpowers/
│       ├── specs/
│       │   ├── 2026-04-22-localsend-inspired-transport-design.md
│       │   └── 2026-04-22-restore-feature-design.md  ← APPROVED SPEC
│       └── plans/
│           ├── 2026-04-22-localsend-transport.md     ← DONE
│           └── 2026-04-22-restore-feature.md         ← IN PROGRESS (Task 1/9)
│
├── lcloud-pc/
│   ├── src/
│   │   ├── main.py              ← entry point: loads cert, starts discovery + server
│   │   ├── config.py            ← ALL constants (port 53317, multicast, cert paths)
│   │   └── core/
│   │       ├── backup_engine.py ← HTTPS server, session mgmt, file streaming
│   │       ├── file_organizer.py← sorts files into Photos/Videos/WhatsApp/Docs/Other
│   │       ├── discovery.py     ← UDP multicast broadcast (sends beacon every 2s)
│   │       ├── certs.py         ← RSA-2048 self-signed cert generation + fingerprint
│   │       └── restore_handler.py ← manifest reader + one-time tokens (v0.3)
│   ├── tests/
│   │   ├── test_backup_engine.py← 8 tests: info, prepare, upload, cancel
│   │   ├── test_certs.py        ← 6 tests: cert generation, fingerprint
│   │   └── test_file_organizer.py
│   ├── requirements.txt         ← cryptography>=42.0.0 (no more zeroconf/requests)
│   ├── Lcloud.spec              ← PyInstaller spec
│   ├── setup.bat
│   └── run.bat
│
└── lcloud-android/
    ├── lib/
    │   ├── main.dart
    │   ├── models/
    │   │   ├── backup_file.dart
    │   │   ├── backup_session.dart
    │   │   └── restore_session.dart  ← RestoreSession/RestoreFile/RestoreFileListing (v0.3)
    │   ├── services/
    │   │   ├── discovery.dart        ← UDP multicast listen + DiscoveredPC model
    │   │   ├── file_scanner.dart
    │   │   ├── transfer_client.dart  ← HTTPS push client (prepareUpload/uploadFile/cancel)
    │   │   └── restore_client.dart   ← HTTPS client for restore endpoints (v0.3)
    │   ├── screens/
    │   │   ├── home_screen.dart      ← Backup Now button, discovery, progress
    │   │   ├── settings_screen.dart
    │   │   └── restore_screen.dart   ← category tabs, session rows, restore flow (v0.3)
    │   └── widgets/
    │       ├── progress_card.dart
    │       └── status_card.dart
    ├── android/app/src/main/kotlin/com/lcloud/lcloud/MainActivity.kt
    │   └─ multicast lock platform channel (com.lcloud.lcloud/multicast)
    ├── pubspec.yaml             ← flutter, permission_handler, crypto, intl, http
    └── test/
        ├── widget_test.dart
        ├── services/transfer_client_test.dart
        └── models/restore_session_test.dart  ← 8 tests for data class parsing (v0.3)
```

---

## v0.3 Restore Feature — Current In-Progress Work

**Status:** ✅ COMPLETE. All 9 tasks done. Binaries rebuilt.

### How Restore Works

After every completed backup, PC writes a manifest:
```
{backup_root}/.lcloud/manifests/{session_id}.json
```
Records each file's `originalPath` (full phone path) and `backedUpPath` (relative to backup_root).

Three new GET endpoints serve restore data. Android has a RestoreScreen with category tabs, expandable session rows, file checkboxes, and a restore loop that skips existing files and handles missing folders.

### Task Status

| # | Task | Status |
|---|------|--------|
| 1 | PC: Add `MANIFEST_SUBDIR` to config.py | ✅ Done |
| 2 | PC: RestoreHandler class (TDD) | ✅ Done |
| 3 | PC: Manifest writing in backup_engine.py | ✅ Done |
| 4 | PC: Wire restore endpoints into HTTPS server | ✅ Done |
| 5 | Android: restore_session.dart data classes + tests | ✅ Done |
| 6 | Android: restore_client.dart HTTPS client | ✅ Done |
| 7 | Android: restore_screen.dart full UI | ✅ Done |
| 8 | Android: Add Restore button to home_screen.dart | ✅ Done |
| 9 | Rebuild Lcloud.exe and lcloud-android.apk | ✅ Done |

---

## Build Environment

| Tool | Location | Notes |
|------|----------|-------|
| Flutter 3.41.6 | `H:\fun\tools\flutter\bin` | Add to PATH or use full path |
| JDK 17 (Microsoft) | `H:\fun\tools\jdk-17.0.18+8` | Flutter configured via `flutter config --jdk-dir` |
| Android SDK | `C:\Users\{user}\AppData\Local\Android\Sdk` |
| Python 3.12 | System PATH |

### How to Run

**PC App:**
```bat
cd lcloud-pc
setup.bat          # first time only — creates venv, installs deps
run.bat            # start the app
```

**Android App:**
```bat
cd lcloud-android
flutter run        # build + deploy to connected phone
```

**Tests:**
```bat
cd lcloud-pc && call venv\Scripts\activate && pytest tests\ -v
cd lcloud-android && flutter test
```

**Rebuild binaries:**
```bat
build-pc.bat       # → H:\fun\lcloud\Lcloud.exe
build-android.bat  # → H:\fun\lcloud\lcloud-android.apk
```

---

## Superpowers — Active Rules

This project uses the `superpowers` plugin system. **Rules:**

1. **Always invoke the relevant skill before acting.** Even a 1% chance a skill applies means invoke it.
2. **Before any new feature:** `superpowers:brainstorming` → design doc first, then plan, then implementation
3. **Implementation:** `superpowers:subagent-driven-development` (user's confirmed preferred approach)
4. **TDD is mandatory:** Write failing test → implement → test passes → commit
5. **After a major step:** `superpowers:code-reviewer`
6. **Commit frequently:** After every task completes, not at the end

---

## Coding Conventions

### Python (PC)
- All constants in `config.py` — no magic strings elsewhere
- All public methods typed, no `type: ignore`
- `logging` not `print`
- Tests: `pytest tests\ -v` — all must pass before commit

### Dart (Android)
- Follow `analysis_options.yaml` — `flutter analyze` before commit
- `final` everywhere possible
- Tests: `flutter test` — all must pass before commit

### Commits
`feat(scope): description` / `fix: description` / `chore: description`

### Never commit
`venv/`, `__pycache__/`, `*.log`, `Lcloud.exe`, `*.apk`, TLS certs (they live in `%LOCALAPPDATA%\lcloud\` at runtime)

---

## Key Design Decisions (Locked In)

| Decision | Why |
|----------|-----|
| LocalSend transport (multicast UDP + HTTPS push) | mDNS was broken by Windows Firewall; proven pattern |
| Port 53317 | Known-open on most home routers (same as LocalSend) |
| Self-signed cert + SHA-256 fingerprint TOFU | No CA needed, zero config for user |
| Push model (phone → PC) | Real progress tracking, simpler phone side |
| Manifest for restore: per-session JSON, relative paths | Decoupled from backup; survives folder moves |
| No account ever | Core trust signal; shapes entire architecture |
| Python + CustomTkinter | Fast to build, readable for contributors |
| Flutter/Dart | Cross-platform (iOS later without rewrite) |

---

## What Is NOT Built Yet

- Priority engine (WhatsApp → Photos → Videos → Docs)
- Storage threshold trigger (15% free → auto-backup)
- "Delete after backup" actual file deletion (stub dialog exists)
- Duplicate detection (SHA-256)
- Resume interrupted backups
- AES-256 at-rest encryption
- Windows background service / auto-start
- Open source release

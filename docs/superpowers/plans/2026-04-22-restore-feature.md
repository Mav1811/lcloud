# Restore Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow the Android app to browse backed-up files by session/category and restore them to their exact original phone location over the same HTTPS connection used for backup.

**Architecture:** The PC writes a `manifest.json` after each completed backup session recording each file's original phone path and its backed-up relative path. Three new GET endpoints on the existing HTTPS server let the Android app list sessions, get file listings with one-time tokens, and stream individual files back. The Android side adds a RestoreScreen with category tabs, expandable session rows, checkboxes, and a progress view that reuses the existing `ProgressCard` widget.

**Tech Stack:** Python 3.12 (PC server), `pathlib`, `json`, `mimetypes`, `uuid`; Flutter/Dart (Android), `dart:io`, `crypto`, `intl`

---

## File Map

### PC (`lcloud-pc/`)

| File | Action | Responsibility |
|------|--------|----------------|
| `src/config.py` | Modify | Add `MANIFEST_SUBDIR` constant |
| `src/core/restore_handler.py` | **Create** | Reads manifests, manages one-time tokens, implements endpoint logic |
| `src/core/backup_engine.py` | Modify | Add `backed_up_path`/`device_alias`/`started_at` to dataclasses; capture `organize()` return; write manifest on session complete; wire restore endpoints into `do_GET` |
| `tests/test_restore_handler.py` | **Create** | TDD tests for RestoreHandler (direct, no HTTP) |
| `tests/test_backup_engine.py` | Modify | Add `TestManifest` + `TestRestoreEndpoints` classes |

### Android (`lcloud-android/`)

| File | Action | Responsibility |
|------|--------|----------------|
| `lib/models/restore_session.dart` | **Create** | `RestoreSession`, `RestoreFile`, `RestoreFileListing` data classes |
| `lib/services/restore_client.dart` | **Create** | HTTPS client: getSessions, getFiles, downloadFile |
| `lib/screens/restore_screen.dart` | **Create** | Full restore UI: category tabs, session rows, file checkboxes, restore loop |
| `lib/screens/home_screen.dart` | Modify | Add "Restore" outlined button below "Backup Now" |
| `test/models/restore_session_test.dart` | **Create** | Unit tests for data class parsing |

---

## Task 1: PC — Add MANIFEST_SUBDIR to config.py

**Files:**
- Modify: `lcloud-pc/src/config.py`

- [ ] **Step 1: Add the constant**

Open `lcloud-pc/src/config.py`. After the `CATEGORY_FOLDERS` block (around line 37), add:

```python
# Restore manifests — written after every completed backup session
MANIFEST_SUBDIR = ".lcloud/manifests"   # relative to backup_root
```

- [ ] **Step 2: Verify the file loads**

```bat
cd lcloud-pc
call venv\Scripts\activate
python -c "from config import MANIFEST_SUBDIR; print(MANIFEST_SUBDIR)"
```

Expected output: `.lcloud/manifests`

- [ ] **Step 3: Commit**

```bat
git add lcloud-pc/src/config.py
git commit -m "feat(restore): add MANIFEST_SUBDIR constant to config"
```

---

## Task 2: PC — RestoreHandler class (TDD)

**Files:**
- Create: `lcloud-pc/src/core/restore_handler.py`
- Create: `lcloud-pc/tests/test_restore_handler.py`

- [ ] **Step 1: Write the failing tests**

Create `lcloud-pc/tests/test_restore_handler.py`:

```python
"""Tests for RestoreHandler — reads manifests + issues one-time tokens."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.restore_handler import RestoreHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _manifest_dir(backup_root: Path) -> Path:
    d = backup_root / ".lcloud" / "manifests"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_manifest(
    backup_root: Path,
    session_id: str,
    files: list[dict],
    device_alias: str = "Pixel 7",
) -> None:
    data = {
        "sessionId": session_id,
        "startedAt": "2026-04-20T10:30:00",
        "completedAt": "2026-04-20T10:45:00",
        "deviceAlias": device_alias,
        "files": files,
    }
    path = _manifest_dir(backup_root) / f"{session_id}.json"
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# get_sessions
# ---------------------------------------------------------------------------

class TestGetSessions:
    def test_no_manifest_dir_returns_empty(self, tmp_path):
        handler = RestoreHandler()
        assert handler.get_sessions(tmp_path) == []

    def test_empty_manifest_dir_returns_empty(self, tmp_path):
        _manifest_dir(tmp_path)
        handler = RestoreHandler()
        assert handler.get_sessions(tmp_path) == []

    def test_returns_summary_for_one_session(self, tmp_path):
        _write_manifest(tmp_path, "sess-1", [
            {
                "fileId": "f1", "fileName": "photo.jpg",
                "originalPath": "/DCIM/photo.jpg",
                "backedUpPath": "Photos/2026/04/photo.jpg",
                "category": "photo", "sizeBytes": 3000,
                "modifiedAt": "2026-04-19T10:00:00",
            }
        ])
        handler = RestoreHandler()
        sessions = handler.get_sessions(tmp_path)
        assert len(sessions) == 1
        s = sessions[0]
        assert s["sessionId"] == "sess-1"
        assert s["deviceAlias"] == "Pixel 7"
        assert s["fileCount"] == 1
        assert s["totalBytes"] == 3000
        assert "startedAt" in s
        assert "completedAt" in s

    def test_skips_corrupt_manifest_and_returns_rest(self, tmp_path):
        corrupt = _manifest_dir(tmp_path) / "bad.json"
        corrupt.write_text("not json", encoding="utf-8")
        _write_manifest(tmp_path, "sess-good", [])
        handler = RestoreHandler()
        sessions = handler.get_sessions(tmp_path)
        assert len(sessions) == 1
        assert sessions[0]["sessionId"] == "sess-good"

    def test_multiple_sessions_returned(self, tmp_path):
        _write_manifest(tmp_path, "sess-a", [])
        _write_manifest(tmp_path, "sess-b", [])
        handler = RestoreHandler()
        sessions = handler.get_sessions(tmp_path)
        assert len(sessions) == 2


# ---------------------------------------------------------------------------
# get_files
# ---------------------------------------------------------------------------

class TestGetFiles:
    def test_unknown_session_returns_none(self, tmp_path):
        _manifest_dir(tmp_path)
        handler = RestoreHandler()
        assert handler.get_files(tmp_path, "no-such-session") is None

    def test_available_file_gets_token(self, tmp_path):
        # Create the backed-up file on disk
        dest = tmp_path / "Photos" / "2026" / "04" / "photo.jpg"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"fakeimage")

        _write_manifest(tmp_path, "sess-1", [
            {
                "fileId": "f1", "fileName": "photo.jpg",
                "originalPath": "/DCIM/photo.jpg",
                "backedUpPath": "Photos/2026/04/photo.jpg",
                "category": "photo", "sizeBytes": 9,
                "modifiedAt": "2026-04-19T10:00:00",
            }
        ])
        handler = RestoreHandler()
        result = handler.get_files(tmp_path, "sess-1")

        assert result is not None
        assert result["sessionId"] == "sess-1"
        assert len(result["files"]) == 1
        f = result["files"][0]
        assert f["fileId"] == "f1"
        assert f["available"] is True
        assert "f1" in result["tokens"]

    def test_missing_backed_up_file_is_unavailable_with_no_token(self, tmp_path):
        _write_manifest(tmp_path, "sess-1", [
            {
                "fileId": "f1", "fileName": "photo.jpg",
                "originalPath": "/DCIM/photo.jpg",
                "backedUpPath": "Photos/2026/04/gone.jpg",   # not on disk
                "category": "photo", "sizeBytes": 100,
                "modifiedAt": "2026-04-19T10:00:00",
            }
        ])
        handler = RestoreHandler()
        result = handler.get_files(tmp_path, "sess-1")

        assert result["files"][0]["available"] is False
        assert "f1" not in result["tokens"]

    def test_category_filter_excludes_other_categories(self, tmp_path):
        _write_manifest(tmp_path, "sess-1", [
            {
                "fileId": "f1", "fileName": "photo.jpg", "originalPath": "/p.jpg",
                "backedUpPath": "Photos/p.jpg", "category": "photo",
                "sizeBytes": 100, "modifiedAt": "2026-04-19T10:00:00",
            },
            {
                "fileId": "f2", "fileName": "clip.mp4", "originalPath": "/c.mp4",
                "backedUpPath": "Videos/c.mp4", "category": "video",
                "sizeBytes": 200, "modifiedAt": "2026-04-19T10:00:00",
            },
        ])
        handler = RestoreHandler()
        result = handler.get_files(tmp_path, "sess-1", category="photo")

        assert len(result["files"]) == 1
        assert result["files"][0]["fileId"] == "f1"

    def test_no_category_filter_returns_all(self, tmp_path):
        _write_manifest(tmp_path, "sess-1", [
            {
                "fileId": "f1", "fileName": "photo.jpg", "originalPath": "/p.jpg",
                "backedUpPath": "Photos/p.jpg", "category": "photo",
                "sizeBytes": 100, "modifiedAt": "2026-04-19T10:00:00",
            },
            {
                "fileId": "f2", "fileName": "clip.mp4", "originalPath": "/c.mp4",
                "backedUpPath": "Videos/c.mp4", "category": "video",
                "sizeBytes": 200, "modifiedAt": "2026-04-19T10:00:00",
            },
        ])
        handler = RestoreHandler()
        result = handler.get_files(tmp_path, "sess-1", category=None)

        assert len(result["files"]) == 2


# ---------------------------------------------------------------------------
# resolve_token
# ---------------------------------------------------------------------------

class TestResolveToken:
    def _setup_available_file(self, tmp_path: Path) -> tuple["RestoreHandler", str]:
        dest = tmp_path / "Photos" / "2026" / "04" / "photo.jpg"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"data")
        _write_manifest(tmp_path, "sess-1", [
            {
                "fileId": "f1", "fileName": "photo.jpg",
                "originalPath": "/DCIM/photo.jpg",
                "backedUpPath": "Photos/2026/04/photo.jpg",
                "category": "photo", "sizeBytes": 4,
                "modifiedAt": "2026-04-19T10:00:00",
            }
        ])
        handler = RestoreHandler()
        result = handler.get_files(tmp_path, "sess-1")
        token = result["tokens"]["f1"]
        return handler, token

    def test_valid_token_returns_file_path(self, tmp_path):
        handler, token = self._setup_available_file(tmp_path)
        path = handler.resolve_token(token)
        assert path is not None
        assert "photo.jpg" in path

    def test_token_is_consumed_on_first_use(self, tmp_path):
        handler, token = self._setup_available_file(tmp_path)
        handler.resolve_token(token)
        # Second call: consumed → None
        assert handler.resolve_token(token) is None

    def test_unknown_token_returns_none(self):
        handler = RestoreHandler()
        assert handler.resolve_token("fake-token-xyz") is None
```

- [ ] **Step 2: Run tests — expect ImportError (file doesn't exist yet)**

```bat
cd lcloud-pc
call venv\Scripts\activate
pytest tests\test_restore_handler.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.restore_handler'`

- [ ] **Step 3: Create restore_handler.py**

Create `lcloud-pc/src/core/restore_handler.py`:

```python
"""
Lcloud PC — Restore Handler

Reads backup session manifests and serves three restore endpoints:
  GET /api/lcloud/v2/restore/sessions   — list all sessions
  GET /api/lcloud/v2/restore/files      — list files + issue one-time tokens
  GET /api/lcloud/v2/restore/file       — stream one file (token consumed on use)
"""
import json
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

MANIFEST_SUBDIR = ".lcloud/manifests"


class RestoreHandler:
    """
    Stateful handler for restore operations.

    Each BackupEngine instance holds one RestoreHandler. Tokens are in-memory
    one-time keys: generated in get_files(), consumed in resolve_token().
    """

    def __init__(self) -> None:
        # token → absolute path of the backed-up file (string for JSON safety)
        self._tokens: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API (called by _Handler methods in backup_engine.py)
    # ------------------------------------------------------------------

    def get_sessions(self, backup_root: Path) -> list[dict]:
        """Return all readable sessions, newest first (by filename sort)."""
        manifest_dir = backup_root / MANIFEST_SUBDIR
        if not manifest_dir.exists():
            return []

        sessions: list[dict] = []
        for path in sorted(manifest_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                total_bytes = sum(
                    f.get("sizeBytes", 0) for f in data.get("files", [])
                )
                sessions.append({
                    "sessionId":   data["sessionId"],
                    "startedAt":   data["startedAt"],
                    "completedAt": data["completedAt"],
                    "deviceAlias": data.get("deviceAlias", "Unknown"),
                    "fileCount":   len(data.get("files", [])),
                    "totalBytes":  total_bytes,
                })
            except (json.JSONDecodeError, KeyError, OSError) as exc:
                logger.warning("Skipping corrupt manifest %s: %s", path.name, exc)

        return sessions

    def get_files(
        self,
        backup_root: Path,
        session_id: str,
        category: str | None = None,
    ) -> dict | None:
        """
        Return file listing + fresh tokens for a session.

        Returns None if session_id not found. Tokens are only issued for
        files whose backed-up copy exists on disk (available == True).
        """
        manifest_path = backup_root / MANIFEST_SUBDIR / f"{session_id}.json"
        if not manifest_path.exists():
            return None

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Cannot read manifest %s: %s", manifest_path.name, exc)
            return None

        files: list[dict] = []
        tokens: dict[str, str] = {}

        for f in data.get("files", []):
            file_category = f.get("category", "other")
            if category is not None and file_category != category:
                continue

            backed_up = backup_root / f["backedUpPath"]
            available = backed_up.exists()

            file_id = f["fileId"]
            if available:
                token = str(uuid.uuid4())
                self._tokens[token] = str(backed_up)
                tokens[file_id] = token

            files.append({
                "fileId":       file_id,
                "fileName":     f["fileName"],
                "originalPath": f["originalPath"],
                "category":     file_category,
                "sizeBytes":    f.get("sizeBytes", 0),
                "modifiedAt":   f.get("modifiedAt", ""),
                "available":    available,
            })

        return {"sessionId": session_id, "files": files, "tokens": tokens}

    def resolve_token(self, token: str) -> str | None:
        """
        Return the absolute file path for a one-time token.

        The token is consumed (deleted) on first use. Returns None for
        unknown or already-used tokens.
        """
        return self._tokens.pop(token, None)
```

- [ ] **Step 4: Run tests — expect all to pass**

```bat
pytest tests\test_restore_handler.py -v
```

Expected: **11 tests PASS**

- [ ] **Step 5: Commit**

```bat
git add lcloud-pc/src/core/restore_handler.py lcloud-pc/tests/test_restore_handler.py
git commit -m "feat(restore): RestoreHandler — manifest reader + one-time tokens"
```

---

## Task 3: PC — Manifest writing after backup session completes

**Files:**
- Modify: `lcloud-pc/src/core/backup_engine.py`
- Modify: `lcloud-pc/tests/test_backup_engine.py` (add TestManifest class)

- [ ] **Step 1: Write the failing test for manifest writing**

Add this class at the bottom of `lcloud-pc/tests/test_backup_engine.py`:

```python
class TestManifest:
    def test_manifest_written_after_full_upload(self, engine_with_folder):
        """After a complete backup session, a manifest JSON must exist."""
        engine, backup_folder, _ = engine_with_folder

        _, prep = _post_json(engine.port, "/api/lcloud/v2/prepare-upload", {
            "deviceAlias": "TestPhone",
            "files": [
                {
                    "fileId": "f1", "fileName": "photo.jpg", "size": 3,
                    "fileType": "image/jpeg",
                    "path": "/storage/emulated/0/DCIM/Camera/photo.jpg",
                    "category": "photo", "modifiedAt": "2026-04-19T14:00:00",
                }
            ],
        })
        session_id = prep["sessionId"]
        token = prep["files"]["f1"]

        _post_raw(
            engine.port,
            f"/api/lcloud/v2/upload?sessionId={session_id}&fileId=f1&token={token}",
            b"\xff\xd8\xff",
        )

        manifest_path = backup_folder / ".lcloud" / "manifests" / f"{session_id}.json"
        assert manifest_path.exists(), "manifest file was not created"

        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert data["sessionId"] == session_id
        assert data["deviceAlias"] == "TestPhone"
        assert len(data["files"]) == 1

        f = data["files"][0]
        assert f["fileId"] == "f1"
        assert f["originalPath"] == "/storage/emulated/0/DCIM/Camera/photo.jpg"
        assert f["category"] == "photo"
        assert f["backedUpPath"].endswith("photo.jpg")
        assert "/" in f["backedUpPath"]   # forward slashes (posix)

    def test_no_manifest_written_if_session_cancelled(self, engine_with_folder):
        """Cancelled sessions must NOT produce a manifest."""
        engine, backup_folder, _ = engine_with_folder

        _, prep = _post_json(engine.port, "/api/lcloud/v2/prepare-upload", {
            "deviceAlias": "Phone",
            "files": [
                {
                    "fileId": "f1", "fileName": "x.jpg", "size": 1,
                    "fileType": "image/jpeg", "path": "/x.jpg",
                    "category": "photo", "modifiedAt": "2026-01-01T00:00:00",
                }
            ],
        })
        session_id = prep["sessionId"]

        _post_json(engine.port, f"/api/lcloud/v2/cancel?sessionId={session_id}", {})

        manifest_dir = backup_folder / ".lcloud" / "manifests"
        manifests = list(manifest_dir.glob("*.json")) if manifest_dir.exists() else []
        assert manifests == [], "manifest must not be written for cancelled session"
```

- [ ] **Step 2: Run — expect FAIL**

```bat
pytest tests\test_backup_engine.py::TestManifest -v
```

Expected: both tests FAIL (`AssertionError: manifest file was not created`)

- [ ] **Step 3: Update _FileEntry and _Session dataclasses**

In `lcloud-pc/src/core/backup_engine.py`, update the two dataclasses:

```python
@dataclass
class _FileEntry:
    file_id: str
    file_name: str
    size: int
    file_type: str
    path: str          # original phone path (used as originalPath in manifest)
    category: str
    modified_at: datetime
    token: str = field(default_factory=lambda: str(uuid.uuid4()))
    done: bool = False
    backed_up_path: str = ""   # relative to backup_root (posix), set after organize()


@dataclass
class _Session:
    session_id: str
    files: dict[str, _FileEntry]
    bytes_received: int = 0
    files_done: int = 0
    device_alias: str = ""
    started_at: datetime = field(default_factory=datetime.now)
```

- [ ] **Step 4: Add `device_alias` and `started_at` to session creation in `_handle_prepare`**

In `_handle_prepare`, change the session construction from:

```python
session = _Session(session_id=session_id, files=files)
```

to:

```python
session = _Session(
    session_id=session_id,
    files=files,
    device_alias=body.get("deviceAlias", "Unknown"),
    started_at=datetime.now(),
)
```

- [ ] **Step 5: Capture organize() return value and store backed_up_path**

In `_handle_upload`, change:

```python
            organizer_path = entry.path if entry.path else entry.file_name
            self.engine._organizer.organize(
                source_path=tmp_path,
                original_name=organizer_path,
                backup_root=self.engine.backup_folder,
                modified_at=entry.modified_at,
            )
            tmp_path.unlink(missing_ok=True)
            entry.done = True
```

to:

```python
            organizer_path = entry.path if entry.path else entry.file_name
            dest_path = self.engine._organizer.organize(
                source_path=tmp_path,
                original_name=organizer_path,
                backup_root=self.engine.backup_folder,
                modified_at=entry.modified_at,
            )
            tmp_path.unlink(missing_ok=True)
            try:
                rel = dest_path.relative_to(self.engine.backup_folder)
                entry.backed_up_path = rel.as_posix()
            except ValueError:
                entry.backed_up_path = dest_path.as_posix()
            entry.done = True
```

- [ ] **Step 6: Add `_write_manifest` method to BackupEngine**

Add this method to the `BackupEngine` class (after `stop_server`):

```python
    def _write_manifest(self, session: "_Session") -> None:
        """Write a JSON manifest after a successful backup session."""
        if not self.backup_folder:
            return
        manifest_dir = self.backup_folder / ".lcloud" / "manifests"
        try:
            manifest_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.error("Cannot create manifest directory: %s", exc)
            return

        files_data = [
            {
                "fileId":       entry.file_id,
                "fileName":     entry.file_name,
                "originalPath": entry.path,
                "backedUpPath": entry.backed_up_path,
                "category":     entry.category,
                "sizeBytes":    entry.size,
                "modifiedAt":   entry.modified_at.isoformat(),
            }
            for entry in session.files.values()
            if entry.done and entry.backed_up_path
        ]

        manifest = {
            "sessionId":   session.session_id,
            "startedAt":   session.started_at.isoformat(),
            "completedAt": datetime.now().isoformat(),
            "deviceAlias": session.device_alias,
            "files":       files_data,
        }

        path = manifest_dir / f"{session.session_id}.json"
        try:
            path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            logger.info("Manifest written: %s (%d files)", path.name, len(files_data))
        except OSError as exc:
            logger.error("Failed to write manifest: %s", exc)
```

- [ ] **Step 7: Call _write_manifest when session completes**

In `_handle_upload`, in the block that fires when `done == total`, add the manifest call **before** the `_on_complete` callback. Change:

```python
        if done == total:
            errors = [fid for fid, f in session.files.items() if not f.done]
            if self.engine._on_complete:
                self.engine._on_complete(done, bytes_done, errors)
            with self.engine._lock:
                self.engine._sessions.pop(session_id, None)
            logger.info("Session %s complete: %d files", session_id, done)
```

to:

```python
        if done == total:
            errors = [fid for fid, f in session.files.items() if not f.done]
            self.engine._write_manifest(session)
            if self.engine._on_complete:
                self.engine._on_complete(done, bytes_done, errors)
            with self.engine._lock:
                self.engine._sessions.pop(session_id, None)
            logger.info("Session %s complete: %d files", session_id, done)
```

- [ ] **Step 8: Run manifest tests — expect both to pass**

```bat
pytest tests\test_backup_engine.py::TestManifest -v
```

Expected: **2 tests PASS**

- [ ] **Step 9: Run full test suite to confirm no regressions**

```bat
pytest tests\ -v
```

Expected: **all tests PASS**

- [ ] **Step 10: Commit**

```bat
git add lcloud-pc/src/core/backup_engine.py lcloud-pc/tests/test_backup_engine.py
git commit -m "feat(restore): write manifest.json after each completed backup session"
```

---

## Task 4: PC — Wire restore endpoints into the HTTPS server

**Files:**
- Modify: `lcloud-pc/src/core/backup_engine.py`
- Modify: `lcloud-pc/tests/test_backup_engine.py` (add TestRestoreEndpoints)

- [ ] **Step 1: Write failing endpoint tests**

Add this class at the bottom of `lcloud-pc/tests/test_backup_engine.py`:

```python
class TestRestoreEndpoints:
    """End-to-end tests hitting the live HTTPS server restore endpoints."""

    def _upload_one_file(self, engine, content: bytes = b"\xff\xd8\xff"):
        """Helper: run a full prepare+upload cycle; return (session_id, backup_folder)."""
        _, prep = _post_json(engine.port, "/api/lcloud/v2/prepare-upload", {
            "deviceAlias": "Phone",
            "files": [
                {
                    "fileId": "f1", "fileName": "photo.jpg", "size": len(content),
                    "fileType": "image/jpeg",
                    "path": "/storage/emulated/0/DCIM/photo.jpg",
                    "category": "photo", "modifiedAt": "2026-04-19T10:00:00",
                }
            ],
        })
        session_id = prep["sessionId"]
        token = prep["files"]["f1"]
        _post_raw(
            engine.port,
            f"/api/lcloud/v2/upload?sessionId={session_id}&fileId=f1&token={token}",
            content,
        )
        return session_id

    def test_sessions_returns_list_after_backup(self, engine_with_folder):
        engine, _, _ = engine_with_folder
        self._upload_one_file(engine)

        status, body = _get(engine.port, "/api/lcloud/v2/restore/sessions")
        assert status == 200
        assert "sessions" in body
        assert len(body["sessions"]) == 1
        s = body["sessions"][0]
        assert s["fileCount"] == 1
        assert s["deviceAlias"] == "Phone"

    def test_sessions_404_when_no_backup_folder(self, tmp_path):
        cert_path = tmp_path / "lcloud.crt"
        key_path = tmp_path / "lcloud.key"
        load_or_generate(cert_path, key_path)
        engine = BackupEngine()
        engine.start_server(
            backup_folder=None, cert_path=cert_path, key_path=key_path,
            alias="X", fingerprint="x", port=0,
        )
        try:
            import urllib.error
            try:
                _get(engine.port, "/api/lcloud/v2/restore/sessions")
                assert False, "expected 404"
            except urllib.error.HTTPError as e:
                assert e.code == 404
        finally:
            engine.stop_server()

    def test_restore_files_returns_file_listing(self, engine_with_folder):
        engine, _, _ = engine_with_folder
        session_id = self._upload_one_file(engine)

        status, body = _get(
            engine.port,
            f"/api/lcloud/v2/restore/files?sessionId={session_id}",
        )
        assert status == 200
        assert body["sessionId"] == session_id
        assert len(body["files"]) == 1
        f = body["files"][0]
        assert f["fileId"] == "f1"
        assert f["available"] is True
        assert "f1" in body["tokens"]

    def test_restore_files_404_for_unknown_session(self, engine_with_folder):
        engine, _, _ = engine_with_folder
        import urllib.error
        try:
            _get(engine.port, "/api/lcloud/v2/restore/files?sessionId=no-such-session")
            assert False, "expected 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404

    def test_restore_file_streams_bytes(self, engine_with_folder):
        engine, _, _ = engine_with_folder
        content = b"\xff\xd8\xff" * 10
        self._upload_one_file(engine, content=content)

        # Get token
        _, sessions_body = _get(engine.port, "/api/lcloud/v2/restore/sessions")
        session_id = sessions_body["sessions"][0]["sessionId"]
        _, files_body = _get(
            engine.port,
            f"/api/lcloud/v2/restore/files?sessionId={session_id}",
        )
        token = files_body["tokens"]["f1"]

        # Stream the file
        import ssl
        ctx = _ssl_ctx()
        import urllib.request
        req = urllib.request.Request(
            f"https://127.0.0.1:{engine.port}/api/lcloud/v2/restore/file"
            f"?sessionId={session_id}&fileId=f1&token={token}"
        )
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            body_bytes = resp.read()
        assert body_bytes == content

    def test_restore_file_401_on_bad_token(self, engine_with_folder):
        engine, _, _ = engine_with_folder
        import urllib.error
        try:
            import ssl
            ctx = _ssl_ctx()
            import urllib.request
            req = urllib.request.Request(
                f"https://127.0.0.1:{engine.port}/api/lcloud/v2/restore/file"
                f"?sessionId=x&fileId=y&token=invalid"
            )
            urllib.request.urlopen(req, context=ctx, timeout=5)
            assert False, "expected 401"
        except urllib.error.HTTPError as e:
            assert e.code == 401

    def test_restore_file_token_is_one_time(self, engine_with_folder):
        engine, _, _ = engine_with_folder
        self._upload_one_file(engine)

        _, sessions_body = _get(engine.port, "/api/lcloud/v2/restore/sessions")
        session_id = sessions_body["sessions"][0]["sessionId"]
        _, files_body = _get(
            engine.port,
            f"/api/lcloud/v2/restore/files?sessionId={session_id}",
        )
        token = files_body["tokens"]["f1"]

        # First use: OK
        import urllib.request, urllib.error
        ctx = _ssl_ctx()
        req = urllib.request.Request(
            f"https://127.0.0.1:{engine.port}/api/lcloud/v2/restore/file"
            f"?sessionId={session_id}&fileId=f1&token={token}"
        )
        urllib.request.urlopen(req, context=ctx, timeout=5).close()

        # Second use: 401
        try:
            urllib.request.urlopen(req, context=ctx, timeout=5)
            assert False, "expected 401 on second use"
        except urllib.error.HTTPError as e:
            assert e.code == 401
```

- [ ] **Step 2: Run tests — expect FAIL**

```bat
pytest tests\test_backup_engine.py::TestRestoreEndpoints -v
```

Expected: tests fail with 404 on the new restore routes.

- [ ] **Step 3: Add RestoreHandler import and instance to BackupEngine**

At the top of `lcloud-pc/src/core/backup_engine.py`, add the import:

```python
from core.restore_handler import RestoreHandler
```

In `BackupEngine.__init__`, add:

```python
        self._restore = RestoreHandler()
```

(Place it after `self._organizer = FileOrganizer()`)

- [ ] **Step 4: Add a mime helper at module level**

Add this function near the top of `backup_engine.py` (after the imports):

```python
import mimetypes


def _content_type(path: Path) -> str:
    ct, _ = mimetypes.guess_type(str(path))
    return ct or "application/octet-stream"
```

- [ ] **Step 5: Update do_GET to parse URL and route restore endpoints**

Replace the entire `do_GET` method in `_Handler` with:

```python
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        route = parsed.path

        if route == "/api/lcloud/v2/info":
            self._json(200, {
                "alias": self.engine.alias,
                "fingerprint": self.engine.fingerprint,
                "deviceType": "desktop",
            })
        elif route == "/api/lcloud/v2/restore/sessions":
            self._handle_restore_sessions()
        elif route == "/api/lcloud/v2/restore/files":
            self._handle_restore_files(params)
        elif route == "/api/lcloud/v2/restore/file":
            self._handle_restore_file(params)
        else:
            self._json(404, {"error": "not_found"})
```

- [ ] **Step 6: Add the three restore handler methods to _Handler**

Add these three methods inside `_Handler` (after `_handle_cancel`):

```python
    def _handle_restore_sessions(self) -> None:
        if not self.engine.backup_folder:
            self._json(404, {"error": "no_backup_folder"})
            return
        sessions = self.engine._restore.get_sessions(self.engine.backup_folder)
        self._json(200, {"sessions": sessions})

    def _handle_restore_files(self, params: dict) -> None:
        session_id = params.get("sessionId", [None])[0]
        category   = params.get("category",  [None])[0]
        if not session_id:
            self._json(400, {"error": "missing_sessionId"})
            return
        if not self.engine.backup_folder:
            self._json(503, {"error": "no_backup_folder"})
            return
        result = self.engine._restore.get_files(
            self.engine.backup_folder, session_id, category
        )
        if result is None:
            self._json(404, {"error": "session_not_found"})
            return
        self._json(200, result)

    def _handle_restore_file(self, params: dict) -> None:
        token = params.get("token", [None])[0]
        if not token:
            self._json(401, {"error": "missing_token"})
            return
        file_path_str = self.engine._restore.resolve_token(token)
        if file_path_str is None:
            self._json(401, {"error": "invalid_or_expired_token"})
            return
        path = Path(file_path_str)
        if not path.exists():
            self._json(404, {"error": "file_not_found"})
            return
        try:
            size = path.stat().st_size
            ct = _content_type(path)
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(size))
            self.end_headers()
            with open(path, "rb") as fh:
                while True:
                    chunk = fh.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except OSError as exc:
            logger.error("Failed to stream restore file: %s", exc)
```

- [ ] **Step 7: Run restore endpoint tests**

```bat
pytest tests\test_backup_engine.py::TestRestoreEndpoints -v
```

Expected: **7 tests PASS**

- [ ] **Step 8: Run full test suite**

```bat
pytest tests\ -v
```

Expected: **all tests PASS**

- [ ] **Step 9: Commit**

```bat
git add lcloud-pc/src/core/backup_engine.py lcloud-pc/tests/test_backup_engine.py
git commit -m "feat(restore): wire GET /restore/sessions /files /file into HTTPS server"
```

---

## Task 5: Android — Data classes + tests

**Files:**
- Create: `lcloud-android/lib/models/restore_session.dart`
- Create: `lcloud-android/test/models/restore_session_test.dart`

- [ ] **Step 1: Create the test file first**

Create `lcloud-android/test/models/restore_session_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:lcloud/models/restore_session.dart';

void main() {
  group('RestoreSession.fromJson', () {
    test('parses all fields correctly', () {
      final json = {
        'sessionId': 'sess-abc',
        'startedAt': '2026-04-20T10:30:00',
        'completedAt': '2026-04-20T10:45:00',
        'deviceAlias': 'Pixel 7',
        'fileCount': 42,
        'totalBytes': 5242880,
      };
      final s = RestoreSession.fromJson(json);
      expect(s.sessionId, 'sess-abc');
      expect(s.deviceAlias, 'Pixel 7');
      expect(s.fileCount, 42);
      expect(s.totalBytes, 5242880);
      expect(s.startedAt, isA<DateTime>());
      expect(s.completedAt, isA<DateTime>());
    });

    test('deviceAlias defaults to Unknown when missing', () {
      final json = {
        'sessionId': 's1',
        'startedAt': '2026-04-20T10:30:00',
        'completedAt': '2026-04-20T10:45:00',
        'fileCount': 0,
        'totalBytes': 0,
      };
      final s = RestoreSession.fromJson(json);
      expect(s.deviceAlias, 'Unknown');
    });

    test('sizeLabel returns MB for large sizes', () {
      final json = {
        'sessionId': 's1', 'startedAt': '2026-04-20T10:30:00',
        'completedAt': '2026-04-20T10:45:00',
        'deviceAlias': 'Phone', 'fileCount': 1,
        'totalBytes': 5242880, // 5 MB
      };
      final s = RestoreSession.fromJson(json);
      expect(s.sizeLabel, contains('MB'));
    });

    test('sizeLabel returns KB for small sizes', () {
      final json = {
        'sessionId': 's1', 'startedAt': '2026-04-20T10:30:00',
        'completedAt': '2026-04-20T10:45:00',
        'deviceAlias': 'Phone', 'fileCount': 1,
        'totalBytes': 512,
      };
      final s = RestoreSession.fromJson(json);
      expect(s.sizeLabel, contains('KB'));
    });
  });

  group('RestoreFile.fromJson', () {
    test('parses all fields correctly', () {
      final json = {
        'fileId': 'f1',
        'fileName': 'photo.jpg',
        'originalPath': '/storage/emulated/0/DCIM/Camera/photo.jpg',
        'category': 'photo',
        'sizeBytes': 3145728,
        'modifiedAt': '2026-04-19T14:22:00',
        'available': true,
      };
      final f = RestoreFile.fromJson(json);
      expect(f.fileId, 'f1');
      expect(f.fileName, 'photo.jpg');
      expect(f.originalPath, '/storage/emulated/0/DCIM/Camera/photo.jpg');
      expect(f.category, 'photo');
      expect(f.sizeBytes, 3145728);
      expect(f.available, isTrue);
    });

    test('available defaults to true when field missing', () {
      final json = {
        'fileId': 'f2', 'fileName': 'doc.pdf',
        'originalPath': '/docs/doc.pdf', 'category': 'document',
        'sizeBytes': 500, 'modifiedAt': '2026-04-19T14:22:00',
      };
      final f = RestoreFile.fromJson(json);
      expect(f.available, isTrue);
    });

    test('sizeLabel formats KB correctly', () {
      final json = {
        'fileId': 'f3', 'fileName': 'small.txt',
        'originalPath': '/small.txt', 'category': 'document',
        'sizeBytes': 2048, 'modifiedAt': '2026-04-19T14:22:00',
        'available': true,
      };
      final f = RestoreFile.fromJson(json);
      expect(f.sizeLabel, contains('KB'));
    });
  });

  group('RestoreFileListing.fromJson', () {
    test('parses session id, files list, and tokens map', () {
      final json = {
        'sessionId': 'sess-1',
        'files': [
          {
            'fileId': 'f1', 'fileName': 'photo.jpg',
            'originalPath': '/DCIM/photo.jpg', 'category': 'photo',
            'sizeBytes': 100, 'modifiedAt': '2026-04-19T10:00:00',
            'available': true,
          }
        ],
        'tokens': {'f1': 'token-abc'},
      };
      final listing = RestoreFileListing.fromJson(json);
      expect(listing.sessionId, 'sess-1');
      expect(listing.files, hasLength(1));
      expect(listing.tokens['f1'], 'token-abc');
    });
  });
}
```

- [ ] **Step 2: Run tests — expect compile error**

```bat
cd lcloud-android
flutter test test/models/restore_session_test.dart
```

Expected: compile error — `restore_session.dart` does not exist.

- [ ] **Step 3: Create the data classes**

Create `lcloud-android/lib/models/restore_session.dart`:

```dart
/// Data classes for the restore feature.
///
/// RestoreSession  — summary from GET /restore/sessions
/// RestoreFile     — one file entry from GET /restore/files
/// RestoreFileListing — full response from GET /restore/files

/// Summary of one backup session (shown in the session list).
class RestoreSession {
  const RestoreSession({
    required this.sessionId,
    required this.startedAt,
    required this.completedAt,
    required this.deviceAlias,
    required this.fileCount,
    required this.totalBytes,
  });

  final String sessionId;
  final DateTime startedAt;
  final DateTime completedAt;
  final String deviceAlias;
  final int fileCount;
  final int totalBytes;

  factory RestoreSession.fromJson(Map<String, dynamic> json) => RestoreSession(
        sessionId:   json['sessionId'] as String,
        startedAt:   DateTime.parse(json['startedAt'] as String),
        completedAt: DateTime.parse(json['completedAt'] as String),
        deviceAlias: json['deviceAlias'] as String? ?? 'Unknown',
        fileCount:   json['fileCount'] as int,
        totalBytes:  json['totalBytes'] as int,
      );

  /// Human-readable size (e.g. "12.4 MB" or "512 KB").
  String get sizeLabel {
    final mb = totalBytes / (1024 * 1024);
    if (mb >= 1) return '${mb.toStringAsFixed(1)} MB';
    return '${(totalBytes / 1024).toStringAsFixed(0)} KB';
  }
}

/// One file entry within a restore session.
class RestoreFile {
  const RestoreFile({
    required this.fileId,
    required this.fileName,
    required this.originalPath,
    required this.category,
    required this.sizeBytes,
    required this.modifiedAt,
    required this.available,
  });

  final String fileId;
  final String fileName;

  /// Absolute path where the file lived on the phone before backup.
  final String originalPath;

  final String category;
  final int sizeBytes;
  final DateTime modifiedAt;

  /// False when the backed-up copy is missing from PC disk.
  final bool available;

  factory RestoreFile.fromJson(Map<String, dynamic> json) => RestoreFile(
        fileId:       json['fileId'] as String,
        fileName:     json['fileName'] as String,
        originalPath: json['originalPath'] as String,
        category:     json['category'] as String? ?? 'other',
        sizeBytes:    json['sizeBytes'] as int,
        modifiedAt:   DateTime.parse(json['modifiedAt'] as String),
        available:    json['available'] as bool? ?? true,
      );

  String get sizeLabel {
    final kb = sizeBytes / 1024;
    if (kb >= 1024) return '${(kb / 1024).toStringAsFixed(1)} MB';
    return '${kb.toStringAsFixed(0)} KB';
  }
}

/// Full response from GET /restore/files — files + one-time tokens.
class RestoreFileListing {
  const RestoreFileListing({
    required this.sessionId,
    required this.files,
    required this.tokens,
  });

  final String sessionId;
  final List<RestoreFile> files;
  final Map<String, String> tokens; // fileId → one-time token

  factory RestoreFileListing.fromJson(Map<String, dynamic> json) =>
      RestoreFileListing(
        sessionId: json['sessionId'] as String,
        files: (json['files'] as List<dynamic>)
            .map((f) => RestoreFile.fromJson(f as Map<String, dynamic>))
            .toList(),
        tokens: (json['tokens'] as Map<String, dynamic>)
            .map((k, v) => MapEntry(k, v as String)),
      );
}
```

- [ ] **Step 4: Run tests — expect all pass**

```bat
flutter test test/models/restore_session_test.dart
```

Expected: **10 tests PASS**

- [ ] **Step 5: Commit**

```bat
git add lib/models/restore_session.dart test/models/restore_session_test.dart
git commit -m "feat(restore): RestoreSession/RestoreFile/RestoreFileListing data classes"
```

---

## Task 6: Android — RestoreClient HTTPS client

**Files:**
- Create: `lcloud-android/lib/services/restore_client.dart`

(No separate test file — HTTPS calls require a live server. The RestoreScreen integration covers this path.)

- [ ] **Step 1: Create restore_client.dart**

Create `lcloud-android/lib/services/restore_client.dart`:

```dart
/// Lcloud Android — Restore Client
///
/// HTTPS client for the three restore endpoints.
/// Uses the same fingerprint-based trust as TransferClient.
library;

import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';

import '../models/restore_session.dart';

/// Thrown when the PC returns a known error code during restore.
class RestoreException implements Exception {
  const RestoreException(this.code, [this.detail = '']);

  final String code;
  final String detail;

  @override
  String toString() => 'RestoreException($code: $detail)';
}

/// HTTPS client for all three restore endpoints.
class RestoreClient {
  RestoreClient({
    required this.pcAddress,
    required this.pcPort,
    required this.fingerprint,
  });

  final String pcAddress;
  final int pcPort;
  final String fingerprint;

  String get _base => 'https://$pcAddress:$pcPort/api/lcloud/v2';

  HttpClient _httpClient() => HttpClient()
    ..connectionTimeout = const Duration(seconds: 15)
    ..badCertificateCallback = (X509Certificate cert, String host, int port) =>
        sha256.convert(cert.der).toString() == fingerprint;

  // ------------------------------------------------------------------
  // GET /restore/sessions
  // ------------------------------------------------------------------

  /// Fetch all backup sessions available for restore, newest first.
  ///
  /// Returns an empty list if no backups exist yet (404 from PC).
  Future<List<RestoreSession>> getSessions() async {
    final client = _httpClient();
    try {
      final req = await client
          .getUrl(Uri.parse('$_base/restore/sessions'))
          .timeout(const Duration(seconds: 15));
      final resp = await req.close().timeout(const Duration(seconds: 15));
      if (resp.statusCode == 404) {
        await resp.drain<void>();
        return [];
      }
      if (resp.statusCode != 200) {
        await resp.drain<void>();
        throw RestoreException('sessions_failed', 'HTTP ${resp.statusCode}');
      }
      final body = await resp.transform(utf8.decoder).join();
      final data = jsonDecode(body) as Map<String, dynamic>;
      return (data['sessions'] as List<dynamic>)
          .map((s) => RestoreSession.fromJson(s as Map<String, dynamic>))
          .toList();
    } finally {
      client.close();
    }
  }

  // ------------------------------------------------------------------
  // GET /restore/files?sessionId=X[&category=Y]
  // ------------------------------------------------------------------

  /// Fetch file listing + fresh one-time tokens for a session.
  ///
  /// Pass [category] to filter: 'photo' | 'video' | 'whatsapp' |
  /// 'document' | 'other'. Omit for all files.
  Future<RestoreFileListing> getFiles(
    String sessionId, {
    String? category,
  }) async {
    final client = _httpClient();
    try {
      var url = '$_base/restore/files?sessionId=${Uri.encodeComponent(sessionId)}';
      if (category != null) {
        url += '&category=${Uri.encodeComponent(category)}';
      }
      final req =
          await client.getUrl(Uri.parse(url)).timeout(const Duration(seconds: 15));
      final resp = await req.close().timeout(const Duration(seconds: 15));
      if (resp.statusCode == 404) {
        await resp.drain<void>();
        throw const RestoreException('session_not_found');
      }
      if (resp.statusCode != 200) {
        await resp.drain<void>();
        throw RestoreException('files_failed', 'HTTP ${resp.statusCode}');
      }
      final body = await resp.transform(utf8.decoder).join();
      return RestoreFileListing.fromJson(
          jsonDecode(body) as Map<String, dynamic>);
    } finally {
      client.close();
    }
  }

  // ------------------------------------------------------------------
  // GET /restore/file?sessionId=X&fileId=Y&token=Z
  // ------------------------------------------------------------------

  /// Stream a backed-up file from PC to [destPath] on the phone.
  ///
  /// [onProgress] is called after each chunk with total bytes received.
  /// Throws [RestoreException] on 401 (bad/expired token) or 404.
  Future<void> downloadFile({
    required String sessionId,
    required String fileId,
    required String token,
    required String destPath,
    void Function(int bytesReceived)? onProgress,
  }) async {
    final client = _httpClient();
    try {
      final url = '$_base/restore/file'
          '?sessionId=${Uri.encodeComponent(sessionId)}'
          '&fileId=${Uri.encodeComponent(fileId)}'
          '&token=${Uri.encodeComponent(token)}';

      final req =
          await client.getUrl(Uri.parse(url)).timeout(const Duration(seconds: 60));
      final resp = await req.close().timeout(const Duration(seconds: 60));

      if (resp.statusCode == 401) {
        await resp.drain<void>();
        throw const RestoreException('invalid_token');
      }
      if (resp.statusCode == 404) {
        await resp.drain<void>();
        throw const RestoreException('file_not_found');
      }
      if (resp.statusCode != 200) {
        await resp.drain<void>();
        throw RestoreException('download_failed', 'HTTP ${resp.statusCode}');
      }

      // Create parent directories if needed, then stream to disk
      final dest = File(destPath);
      await dest.parent.create(recursive: true);
      final sink = dest.openWrite();
      int received = 0;
      try {
        await for (final chunk in resp) {
          sink.add(chunk);
          received += chunk.length;
          onProgress?.call(received);
        }
      } finally {
        await sink.close();
      }
    } finally {
      client.close();
    }
  }
}
```

- [ ] **Step 2: Verify it compiles**

```bat
cd lcloud-android
flutter analyze lib/services/restore_client.dart
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bat
git add lib/services/restore_client.dart
git commit -m "feat(restore): RestoreClient HTTPS client for restore endpoints"
```

---

## Task 7: Android — RestoreScreen

**Files:**
- Create: `lcloud-android/lib/screens/restore_screen.dart`

- [ ] **Step 1: Create restore_screen.dart**

Create `lcloud-android/lib/screens/restore_screen.dart`:

```dart
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/restore_session.dart';
import '../services/discovery.dart';
import '../services/restore_client.dart';
import '../widgets/progress_card.dart';

const Color _bgColor = Color(0xFF1a1a2e);
const Color _cardColor = Color(0xFF16213e);
const Color _accentColor = Color(0xFF4f46e5);
const Color _textSecondary = Color(0xFF94a3b8);

enum _Phase { listing, restoring, done }

/// Full restore UI — browse sessions, pick files, restore to original location.
class RestoreScreen extends StatefulWidget {
  const RestoreScreen({super.key, required this.pc});

  final DiscoveredPC pc;

  @override
  State<RestoreScreen> createState() => _RestoreScreenState();
}

class _RestoreScreenState extends State<RestoreScreen> {
  late final RestoreClient _client;

  _Phase _phase = _Phase.listing;
  List<RestoreSession> _sessions = [];
  bool _loading = true;
  String? _error;

  // Category filter — null means "all"
  String? _category;

  // Expandable session rows
  final Set<String> _expanded = {};
  final Map<String, List<RestoreFile>> _filesBySession = {};
  final Map<String, Map<String, String>> _tokensBySession = {};

  // File selection (fileId)
  final Set<String> _selected = {};

  // Restore progress
  String _currentFile = '';
  int _currentIndex = 0;
  int _totalToRestore = 0;
  int _bytesTransferred = 0;
  int _totalBytes = 0;

  // End-of-restore results
  int _restoredCount = 0;
  int _skippedCount = 0;
  final List<RestoreFile> _failedFiles = [];

  // Missing folder decisions: folderPath → 'create' | 'fallback'
  final Map<String, String> _folderDecisions = {};

  @override
  void initState() {
    super.initState();
    _client = RestoreClient(
      pcAddress: widget.pc.address,
      pcPort: widget.pc.port,
      fingerprint: widget.pc.fingerprint,
    );
    _loadSessions();
  }

  // ---------------------------------------------------------------------------
  // Data loading
  // ---------------------------------------------------------------------------

  Future<void> _loadSessions() async {
    setState(() { _loading = true; _error = null; });
    try {
      final sessions = await _client.getSessions();
      if (mounted) setState(() { _sessions = sessions; _loading = false; });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _toggleExpand(String sessionId) async {
    if (_expanded.contains(sessionId)) {
      setState(() => _expanded.remove(sessionId));
      return;
    }
    setState(() => _expanded.add(sessionId));
    if (!_filesBySession.containsKey(sessionId)) {
      await _loadFiles(sessionId);
    }
  }

  Future<void> _loadFiles(String sessionId) async {
    try {
      final listing = await _client.getFiles(sessionId, category: _category);
      if (mounted) {
        setState(() {
          _filesBySession[sessionId] = listing.files;
          _tokensBySession[sessionId] = listing.tokens;
        });
      }
    } catch (e) {
      if (mounted) {
        _showSnack('Could not load files: $e');
      }
    }
  }

  Future<void> _onCategoryChanged(String? category) async {
    setState(() {
      _category = category;
      _filesBySession.clear();
      _tokensBySession.clear();
      _selected.clear();
    });
    // Reload all expanded sessions under the new filter
    for (final sessionId in List.of(_expanded)) {
      await _loadFiles(sessionId);
    }
  }

  // ---------------------------------------------------------------------------
  // Selection
  // ---------------------------------------------------------------------------

  void _toggleFile(String fileId, bool? checked) {
    setState(() {
      if (checked == true) {
        _selected.add(fileId);
      } else {
        _selected.remove(fileId);
      }
    });
  }

  void _selectAll(String sessionId) {
    final files = _filesBySession[sessionId] ?? [];
    final availableIds = files
        .where((f) => f.available)
        .map((f) => f.fileId)
        .toList();
    setState(() {
      final allSelected = availableIds.every(_selected.contains);
      if (allSelected) {
        _selected.removeAll(availableIds);
      } else {
        _selected.addAll(availableIds);
      }
    });
  }

  int get _selectedCount => _selected.length;

  // ---------------------------------------------------------------------------
  // Restore flow
  // ---------------------------------------------------------------------------

  Future<void> _startRestore() async {
    // Collect selected files across all sessions
    final toRestore = <String, List<RestoreFile>>{};  // sessionId → files
    for (final entry in _filesBySession.entries) {
      final sessionFiles = entry.value
          .where((f) => _selected.contains(f.fileId) && f.available)
          .toList();
      if (sessionFiles.isNotEmpty) {
        toRestore[entry.key] = sessionFiles;
      }
    }
    if (toRestore.isEmpty) return;

    setState(() {
      _phase = _Phase.restoring;
      _restoredCount = 0;
      _skippedCount = 0;
      _failedFiles.clear();
      _folderDecisions.clear();
      _currentFile = '';
      _currentIndex = 0;
      _totalToRestore = toRestore.values.fold(0, (s, l) => s + l.length);
      _totalBytes = toRestore.values
          .expand((l) => l)
          .fold(0, (s, f) => s + f.sizeBytes);
      _bytesTransferred = 0;
    });

    int index = 0;
    for (final sessionEntry in toRestore.entries) {
      final sessionId = sessionEntry.key;
      final files = sessionEntry.value;

      // Refresh tokens for this session before downloading
      RestoreFileListing listing;
      try {
        listing = await _client.getFiles(sessionId, category: _category);
      } catch (e) {
        // If token refresh fails, mark all files in session as failed
        for (final f in files) {
          if (mounted) setState(() => _failedFiles.add(f));
        }
        continue;
      }

      for (final file in files) {
        index++;
        final token = listing.tokens[file.fileId];
        if (token == null) {
          if (mounted) setState(() { _failedFiles.add(file); _currentIndex = index; });
          continue;
        }

        if (mounted) setState(() { _currentFile = file.fileName; _currentIndex = index; });

        final destPath = await _resolveDestination(file);
        if (destPath == null) {
          // null = skip (already exists)
          if (mounted) setState(() => _skippedCount++);
          continue;
        }

        try {
          await _client.downloadFile(
            sessionId: sessionId,
            fileId: file.fileId,
            token: token,
            destPath: destPath,
            onProgress: (bytes) {
              if (mounted) setState(() => _bytesTransferred += bytes);
            },
          );
          if (mounted) setState(() => _restoredCount++);
        } on RestoreException {
          if (mounted) setState(() => _failedFiles.add(file));
        } catch (_) {
          if (mounted) setState(() => _failedFiles.add(file));
        }
      }
    }

    if (mounted) setState(() => _phase = _Phase.done);
  }

  /// Returns the destination path for a file, or null to skip.
  ///
  /// - If file already exists at originalPath → return null (skip).
  /// - If parent folder is missing → prompt user once per folder.
  Future<String?> _resolveDestination(RestoreFile file) async {
    final originalPath = file.originalPath;

    // Skip if already exists
    if (await File(originalPath).exists()) return null;

    final parentPath = _parentDir(originalPath);
    if (await Directory(parentPath).exists()) return originalPath;

    // Folder missing — check decision cache (one prompt per folder)
    if (!_folderDecisions.containsKey(parentPath)) {
      if (!mounted) return null;
      final decision = await _showFolderDialog(parentPath, file.category);
      _folderDecisions[parentPath] = decision;
    }

    if (_folderDecisions[parentPath] == 'create') {
      return originalPath;   // downloadFile creates dirs via dest.parent.create()
    } else {
      // Fallback: Lcloud_Restored/<category>/<filename>
      return '/storage/emulated/0/Lcloud_Restored/${file.category}/${_basename(originalPath)}';
    }
  }

  /// Show a dialog asking what to do with a missing folder.
  /// Returns 'create' or 'fallback'.
  Future<String> _showFolderDialog(String folderPath, String category) async {
    final result = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: const Text(
          'Folder Missing',
          style: TextStyle(color: Colors.white),
        ),
        content: Text(
          'The original folder does not exist:\n$folderPath\n\n'
          'What should Lcloud do?',
          style: const TextStyle(color: _textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop('fallback'),
            child: const Text(
              'Use Lcloud_Restored/',
              style: TextStyle(color: _textSecondary),
            ),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop('create'),
            style: ElevatedButton.styleFrom(backgroundColor: _accentColor),
            child: const Text(
              'Create Folder',
              style: TextStyle(color: Colors.white),
            ),
          ),
        ],
      ),
    );
    return result ?? 'fallback';
  }

  // ---------------------------------------------------------------------------
  // UI helpers
  // ---------------------------------------------------------------------------

  String _parentDir(String path) {
    final i = path.lastIndexOf('/');
    return i > 0 ? path.substring(0, i) : '/';
  }

  String _basename(String path) {
    final i = path.lastIndexOf('/');
    return i >= 0 ? path.substring(i + 1) : path;
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(message),
      backgroundColor: _cardColor,
      behavior: SnackBarBehavior.floating,
    ));
  }

  // ---------------------------------------------------------------------------
  // Build
  // ---------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        title: const Text(
          'Restore',
          style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
        ),
        backgroundColor: _bgColor,
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.white),
        actions: [
          if (_phase == _Phase.listing)
            IconButton(
              icon: const Icon(Icons.refresh, color: Colors.white),
              onPressed: _loadSessions,
            ),
        ],
      ),
      body: _phase == _Phase.done
          ? _buildSummary()
          : Column(
              children: [
                if (_phase == _Phase.listing) _buildCategoryTabs(),
                if (_phase == _Phase.restoring)
                  ProgressCard(
                    currentFile: _currentFile,
                    currentIndex: _currentIndex,
                    totalFiles: _totalToRestore,
                    bytesTransferred: _bytesTransferred,
                    totalBytes: _totalBytes,
                  ),
                Expanded(child: _buildBody()),
                if (_phase == _Phase.listing) _buildRestoreButton(),
              ],
            ),
    );
  }

  Widget _buildCategoryTabs() {
    const cats = [
      (null, 'All'),
      ('photo', 'Photos'),
      ('video', 'Videos'),
      ('whatsapp', 'WhatsApp'),
      ('document', 'Documents'),
    ];
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        children: cats.map((c) {
          final selected = _category == c.$1;
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: ChoiceChip(
              label: Text(c.$2),
              selected: selected,
              onSelected: (_) => _onCategoryChanged(c.$1),
              selectedColor: _accentColor,
              backgroundColor: _cardColor,
              labelStyle: TextStyle(
                color: selected ? Colors.white : _textSecondary,
                fontSize: 13,
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator(color: _accentColor));
    }
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.wifi_off, color: _textSecondary, size: 48),
              const SizedBox(height: 16),
              const Text(
                'Connect to PC first',
                style: TextStyle(color: Colors.white, fontSize: 16),
              ),
              const SizedBox(height: 8),
              ElevatedButton(
                onPressed: _loadSessions,
                style: ElevatedButton.styleFrom(backgroundColor: _accentColor),
                child: const Text('Retry', style: TextStyle(color: Colors.white)),
              ),
            ],
          ),
        ),
      );
    }
    if (_sessions.isEmpty) {
      return const Center(
        child: Text(
          'No backups yet.\nRun a backup first.',
          textAlign: TextAlign.center,
          style: TextStyle(color: _textSecondary, fontSize: 14, height: 1.6),
        ),
      );
    }
    if (_phase == _Phase.restoring) {
      return const Center(
        child: Text(
          'Restoring files...',
          style: TextStyle(color: _textSecondary, fontSize: 14),
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      itemCount: _sessions.length,
      itemBuilder: (_, i) => _buildSessionTile(_sessions[i]),
    );
  }

  Widget _buildSessionTile(RestoreSession session) {
    final expanded = _expanded.contains(session.sessionId);
    final files = _filesBySession[session.sessionId] ?? [];
    final date = DateFormat('MMM d, HH:mm').format(session.completedAt);

    // How many available files in this session are selected
    final sessionSelected = files
        .where((f) => f.available && _selected.contains(f.fileId))
        .length;
    final sessionAvailable = files.where((f) => f.available).length;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: () => _toggleExpand(session.sessionId),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(date,
                            style: const TextStyle(color: Colors.white, fontSize: 13)),
                        const SizedBox(height: 2),
                        Text(
                          '${session.fileCount} files · ${session.sizeLabel} · ${session.deviceAlias}',
                          style: const TextStyle(color: _textSecondary, fontSize: 12),
                        ),
                      ],
                    ),
                  ),
                  if (expanded && sessionAvailable > 0)
                    TextButton(
                      onPressed: () => _selectAll(session.sessionId),
                      child: Text(
                        sessionSelected == sessionAvailable ? 'Deselect All' : 'Select All',
                        style: const TextStyle(color: _accentColor, fontSize: 12),
                      ),
                    ),
                  Icon(
                    expanded ? Icons.expand_less : Icons.expand_more,
                    color: _textSecondary,
                  ),
                ],
              ),
            ),
          ),
          if (expanded) ...[
            const Divider(height: 1, color: Colors.white10),
            if (files.isEmpty)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Center(
                  child: CircularProgressIndicator(color: _accentColor, strokeWidth: 2),
                ),
              )
            else
              ...files.map((f) => _buildFileTile(session.sessionId, f)),
          ],
        ],
      ),
    );
  }

  Widget _buildFileTile(String sessionId, RestoreFile file) {
    final selected = _selected.contains(file.fileId);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      child: Row(
        children: [
          Icon(_categoryIcon(file.category),
              color: file.available ? _accentColor : _textSecondary, size: 20),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  file.fileName,
                  style: TextStyle(
                    color: file.available ? Colors.white : _textSecondary,
                    fontSize: 13,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  file.available ? file.sizeLabel : 'Not found on PC',
                  style: const TextStyle(color: _textSecondary, fontSize: 11),
                ),
              ],
            ),
          ),
          if (file.available)
            Checkbox(
              value: selected,
              onChanged: (v) => _toggleFile(file.fileId, v),
              activeColor: _accentColor,
              side: const BorderSide(color: _textSecondary),
            )
          else
            const SizedBox(width: 24),
        ],
      ),
    );
  }

  IconData _categoryIcon(String category) {
    switch (category) {
      case 'photo':
        return Icons.photo;
      case 'video':
        return Icons.videocam;
      case 'whatsapp':
        return Icons.chat;
      case 'document':
        return Icons.description;
      default:
        return Icons.insert_drive_file;
    }
  }

  Widget _buildRestoreButton() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: SizedBox(
        width: double.infinity,
        height: 52,
        child: ElevatedButton(
          onPressed: _selectedCount == 0 ? null : _startRestore,
          style: ElevatedButton.styleFrom(
            backgroundColor: _accentColor,
            disabledBackgroundColor: Colors.white10,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ),
          child: Text(
            _selectedCount == 0
                ? 'Select files to restore'
                : 'Restore $_selectedCount file${_selectedCount == 1 ? '' : 's'}',
            style: const TextStyle(
                fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white),
          ),
        ),
      ),
    );
  }

  Widget _buildSummary() {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Restore Complete',
            style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 24),
          _summaryRow(Icons.check_circle, const Color(0xFF22c55e),
              '$_restoredCount file${_restoredCount == 1 ? '' : 's'} restored'),
          if (_skippedCount > 0)
            _summaryRow(Icons.skip_next, _textSecondary,
                '$_skippedCount skipped (already on phone)'),
          if (_failedFiles.isNotEmpty)
            _summaryRow(Icons.error, const Color(0xFFf59e0b),
                '${_failedFiles.length} failed'),
          if (_failedFiles.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text('Failed files:',
                style: TextStyle(color: _textSecondary, fontSize: 13)),
            const SizedBox(height: 8),
            ..._failedFiles.map((f) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text(
                    f.fileName,
                    style: const TextStyle(color: Colors.white, fontSize: 13),
                  ),
                )),
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              height: 48,
              child: OutlinedButton(
                onPressed: () {
                  setState(() {
                    _selected
                      ..clear()
                      ..addAll(_failedFiles.map((f) => f.fileId));
                    _phase = _Phase.listing;
                    _failedFiles.clear();
                  });
                },
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: _accentColor),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text('Retry Failed',
                    style: TextStyle(color: _accentColor)),
              ),
            ),
          ],
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            height: 48,
            child: ElevatedButton(
              onPressed: () {
                setState(() {
                  _phase = _Phase.listing;
                  _selected.clear();
                });
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: _accentColor,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12)),
              ),
              child: const Text('Done',
                  style: TextStyle(color: Colors.white, fontSize: 16)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _summaryRow(IconData icon, Color color, String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 12),
          Text(text, style: const TextStyle(color: Colors.white, fontSize: 15)),
        ],
      ),
    );
  }
}
```

- [ ] **Step 2: Analyze for errors**

```bat
cd lcloud-android
flutter analyze lib/screens/restore_screen.dart
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bat
git add lib/screens/restore_screen.dart
git commit -m "feat(restore): RestoreScreen — sessions, file picker, restore flow, summary"
```

---

## Task 8: Android — Add Restore button to HomeScreen

**Files:**
- Modify: `lcloud-android/lib/screens/home_screen.dart`

- [ ] **Step 1: Add the import for RestoreScreen at the top of home_screen.dart**

In `lcloud-android/lib/screens/home_screen.dart`, add this import after the existing imports:

```dart
import 'restore_screen.dart';
```

- [ ] **Step 2: Add the Restore button below the Backup Now button**

In `home_screen.dart`, find the `Padding` widget that wraps the Backup Now `ElevatedButton` (around line 351). Add the Restore outlined button directly after its closing `,`:

```dart
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: SizedBox(
              width: double.infinity,
              height: 52,
              child: ElevatedButton(
                onPressed: (_backingUp || _pc == null) ? null : _startBackup,
                style: ElevatedButton.styleFrom(
                  backgroundColor: _accentColor,
                  disabledBackgroundColor: Colors.white10,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                ),
                child: Text(
                  _backingUp ? 'Backing up...' : 'Backup Now',
                  style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: Colors.white),
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: SizedBox(
              width: double.infinity,
              height: 48,
              child: OutlinedButton(
                onPressed: _pc == null
                    ? null
                    : () => Navigator.push(
                          context,
                          MaterialPageRoute<void>(
                            builder: (_) => RestoreScreen(pc: _pc!),
                          ),
                        ),
                style: OutlinedButton.styleFrom(
                  side: BorderSide(
                      color: _pc == null ? Colors.white24 : _accentColor),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                ),
                child: Text(
                  'Restore',
                  style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w500,
                      color: _pc == null ? Colors.white24 : _accentColor),
                ),
              ),
            ),
          ),
```

- [ ] **Step 3: Analyze the modified file**

```bat
flutter analyze lib/screens/home_screen.dart
```

Expected: no errors.

- [ ] **Step 4: Run the full Android test suite**

```bat
flutter test
```

Expected: all existing tests pass (smoke test + services tests + new model tests).

- [ ] **Step 5: Commit**

```bat
git add lib/screens/home_screen.dart
git commit -m "feat(restore): add Restore button to HomeScreen → navigates to RestoreScreen"
```

---

## Task 9: Rebuild binaries

- [ ] **Step 1: Run the full PC test suite one final time**

```bat
cd lcloud-pc
call venv\Scripts\activate
pytest tests\ -v
```

Expected: all tests pass.

- [ ] **Step 2: Build the PC executable**

```bat
cd lcloud-pc
call venv\Scripts\activate
pyinstaller Lcloud.spec --clean --noconfirm
```

Expected: `dist\Lcloud.exe` created (~23 MB).

- [ ] **Step 3: Replace the old exe**

```bat
del H:\fun\lcloud\Lcloud.exe
copy lcloud-pc\dist\Lcloud.exe H:\fun\lcloud\Lcloud.exe
```

- [ ] **Step 4: Build the Android APK**

```bat
cd lcloud-android
flutter build apk --release
```

Expected: `build\app\outputs\flutter-apk\app-release.apk` created.

- [ ] **Step 5: Replace the old APK**

```bat
del H:\fun\lcloud\lcloud-android.apk
copy build\app\outputs\flutter-apk\app-release.apk H:\fun\lcloud\lcloud-android.apk
```

- [ ] **Step 6: Final commit**

```bat
cd H:\fun\lcloud
git add Lcloud.exe lcloud-android.apk
git commit -m "release: Lcloud v0.3 — restore feature (manifests + 3 endpoints + RestoreScreen)"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|-----------------|------------|
| Manifest written after each completed backup session | Task 3 |
| `originalPath` + `backedUpPath` (relative) in manifest | Task 3 |
| `fileId` same as upload session | Task 3 (reuses `_FileEntry.file_id`) |
| GET /restore/sessions | Task 4 |
| GET /restore/files?sessionId&category | Task 4 |
| GET /restore/file?sessionId&fileId&token | Task 4 |
| One-time tokens | Task 2 (RestoreHandler._tokens) |
| `available: false` for missing files | Task 2 |
| Android data classes RestoreSession/RestoreFile | Task 5 |
| RestoreClient.getSessions/getFiles/downloadFile | Task 6 |
| Category filter tabs | Task 7 |
| Expandable session rows | Task 7 |
| File checkboxes | Task 7 |
| Select All per session | Task 7 |
| Restore button with count | Task 7 |
| Skip existing files (no overwrite) | Task 7 (`_resolveDestination` checks File.exists) |
| Missing folder: Create OR Lcloud_Restored/ | Task 7 (`_showFolderDialog`) |
| One prompt per unique missing folder | Task 7 (`_folderDecisions` cache) |
| Per-file failure never stops rest | Task 7 (try/catch continues loop) |
| End summary: restored / skipped / failed | Task 7 (`_buildSummary`) |
| Retry failed button | Task 7 (`_buildSummary`) |
| Restore button on HomeScreen | Task 8 |
| Fingerprint cert verification | Task 6 (RestoreClient reuses same pattern) |
| 404 if manifest dir missing | Task 4 (`_handle_restore_sessions` checks backup_folder) |

All spec requirements are covered. No placeholders, no TODOs.

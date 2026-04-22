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
                "backedUpPath": "Photos/2026/04/gone.jpg",
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
        assert handler.resolve_token(token) is None

    def test_unknown_token_returns_none(self):
        handler = RestoreHandler()
        assert handler.resolve_token("fake-token-xyz") is None

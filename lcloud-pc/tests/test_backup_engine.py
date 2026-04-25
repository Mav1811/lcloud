"""Tests for the HTTPS backup engine (session management + file upload)."""
import collections
import json
import shutil
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.backup_engine import BackupEngine
from core.certs import load_or_generate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine_with_folder(tmp_path):
    """Start a real HTTPS engine on an ephemeral port; yield it; shut it down."""
    cert_path = tmp_path / "lcloud.crt"
    key_path = tmp_path / "lcloud.key"
    load_or_generate(cert_path, key_path)

    engine = BackupEngine()
    backup_folder = tmp_path / "backup"
    backup_folder.mkdir()

    engine.start_server(
        backup_folder=backup_folder,
        cert_path=cert_path,
        key_path=key_path,
        alias="TestPC",
        fingerprint="test-fp",
        port=0,  # OS picks an ephemeral port
    )
    yield engine, backup_folder, cert_path
    engine.stop_server()


def _ssl_ctx() -> ssl.SSLContext:
    """Client SSL context that skips cert verification (self-signed)."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _get(port, path):
    ctx = _ssl_ctx()
    req = urllib.request.Request(f"https://127.0.0.1:{port}{path}")
    with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


def _post_json(port, path, body_dict):
    ctx = _ssl_ctx()
    body = json.dumps(body_dict).encode()
    req = urllib.request.Request(
        f"https://127.0.0.1:{port}{path}", data=body, method="POST"
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Content-Length", str(len(body)))
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post_raw(port, path, data: bytes):
    ctx = _ssl_ctx()
    req = urllib.request.Request(
        f"https://127.0.0.1:{port}{path}", data=data, method="POST"
    )
    req.add_header("Content-Type", "application/octet-stream")
    req.add_header("Content-Length", str(len(data)))
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInfoEndpoint:
    def test_returns_alias_and_fingerprint(self, engine_with_folder):
        engine, _, _ = engine_with_folder
        status, body = _get(engine.port, "/api/lcloud/v2/info")
        assert status == 200
        assert body["alias"] == "TestPC"
        assert body["fingerprint"] == "test-fp"
        assert body["deviceType"] == "desktop"


class TestPrepareUpload:
    def test_returns_session_and_tokens(self, engine_with_folder):
        engine, _, _ = engine_with_folder
        status, body = _post_json(engine.port, "/api/lcloud/v2/prepare-upload", {
            "deviceAlias": "TestPhone",
            "files": [
                {"fileId": "f1", "fileName": "a.jpg", "size": 100,
                 "fileType": "image/jpeg", "path": "/DCIM/a.jpg",
                 "category": "photo", "modifiedAt": "2026-01-01T00:00:00"},
            ],
        })
        assert status == 200
        assert "sessionId" in body
        assert "f1" in body["files"]

    def test_503_when_no_backup_folder(self, tmp_path):
        cert_path = tmp_path / "lcloud.crt"
        key_path = tmp_path / "lcloud.key"
        load_or_generate(cert_path, key_path)
        engine = BackupEngine()
        engine.start_server(
            backup_folder=None,
            cert_path=cert_path,
            key_path=key_path,
            alias="X",
            fingerprint="x",
            port=0,
        )
        try:
            status, body = _post_json(engine.port, "/api/lcloud/v2/prepare-upload", {
                "deviceAlias": "Phone", "files": [],
            })
            assert status == 503
            assert body["error"] == "no_backup_folder"
        finally:
            engine.stop_server()

    def test_507_when_disk_too_full(self, engine_with_folder, monkeypatch):
        engine, _, _ = engine_with_folder
        DiskUsage = collections.namedtuple("usage", ["total", "used", "free"])
        monkeypatch.setattr(
            shutil, "disk_usage",
            lambda _: DiskUsage(1_000_000, 999_000, 1_000),
        )
        status, body = _post_json(engine.port, "/api/lcloud/v2/prepare-upload", {
            "deviceAlias": "Phone",
            "files": [{"fileId": "f1", "fileName": "big.mp4", "size": 500_000_000,
                       "fileType": "video/mp4", "path": "/big.mp4",
                       "category": "video", "modifiedAt": "2026-01-01T00:00:00"}],
        })
        assert status == 507
        assert body["error"] == "insufficient_storage"


class TestUpload:
    def test_full_upload_flow_saves_file(self, engine_with_folder):
        engine, backup_folder, _ = engine_with_folder

        _, prep = _post_json(engine.port, "/api/lcloud/v2/prepare-upload", {
            "deviceAlias": "Phone",
            "files": [{"fileId": "f1", "fileName": "photo.jpg", "size": 3,
                       "fileType": "image/jpeg", "path": "/DCIM/photo.jpg",
                       "category": "photo", "modifiedAt": "2026-01-01T10:00:00"}],
        })
        session_id = prep["sessionId"]
        token = prep["files"]["f1"]

        status, body = _post_raw(
            engine.port,
            f"/api/lcloud/v2/upload?sessionId={session_id}&fileId=f1&token={token}",
            b"\xff\xd8\xff",
        )
        assert status == 200
        assert body["success"] is True

        saved = [f for f in backup_folder.rglob("*") if f.is_file() and ".lcloud" not in f.parts]
        assert len(saved) == 1

    def test_401_on_bad_token(self, engine_with_folder):
        engine, _, _ = engine_with_folder

        _, prep = _post_json(engine.port, "/api/lcloud/v2/prepare-upload", {
            "deviceAlias": "Phone",
            "files": [{"fileId": "f1", "fileName": "x.jpg", "size": 1,
                       "fileType": "image/jpeg", "path": "/x.jpg",
                       "category": "photo", "modifiedAt": "2026-01-01T00:00:00"}],
        })
        session_id = prep["sessionId"]

        status, _ = _post_raw(
            engine.port,
            f"/api/lcloud/v2/upload?sessionId={session_id}&fileId=f1&token=WRONG",
            b"x",
        )
        assert status == 401

    def test_progress_callback_fires(self, engine_with_folder):
        engine, _, _ = engine_with_folder
        progress_calls = []
        engine._on_progress = lambda *args: progress_calls.append(args)

        _, prep = _post_json(engine.port, "/api/lcloud/v2/prepare-upload", {
            "deviceAlias": "Phone",
            "files": [{"fileId": "f1", "fileName": "x.jpg", "size": 1,
                       "fileType": "image/jpeg", "path": "/x.jpg",
                       "category": "photo", "modifiedAt": "2026-01-01T00:00:00"}],
        })
        session_id = prep["sessionId"]
        token = prep["files"]["f1"]

        _post_raw(
            engine.port,
            f"/api/lcloud/v2/upload?sessionId={session_id}&fileId=f1&token={token}",
            b"x",
        )
        assert len(progress_calls) == 1
        filename, index, total, _, _ = progress_calls[0]
        assert filename == "x.jpg"
        assert index == 1
        assert total == 1


class TestCancel:
    def test_cancel_removes_session(self, engine_with_folder):
        engine, _, _ = engine_with_folder

        _, prep = _post_json(engine.port, "/api/lcloud/v2/prepare-upload", {
            "deviceAlias": "Phone",
            "files": [{"fileId": "f1", "fileName": "x.jpg", "size": 1,
                       "fileType": "image/jpeg", "path": "/x.jpg",
                       "category": "photo", "modifiedAt": "2026-01-01T00:00:00"}],
        })
        session_id = prep["sessionId"]

        status, body = _post_json(
            engine.port, f"/api/lcloud/v2/cancel?sessionId={session_id}", {}
        )
        assert status == 200
        assert body["cancelled"] is True

        # Upload after cancel must 401 (session gone)
        status2, _ = _post_raw(
            engine.port,
            f"/api/lcloud/v2/upload?sessionId={session_id}&fileId=f1&token=any",
            b"x",
        )
        assert status2 == 401


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


class TestRestoreEndpoints:
    """End-to-end tests hitting the live HTTPS server restore endpoints."""

    def _upload_one_file(self, engine, content: bytes = b"\xff\xd8\xff"):
        """Helper: run a full prepare+upload cycle; return session_id."""
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
        try:
            _get(engine.port, "/api/lcloud/v2/restore/files?sessionId=no-such-session")
            assert False, "expected 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404

    def test_restore_file_streams_bytes(self, engine_with_folder):
        engine, _, _ = engine_with_folder
        content = b"\xff\xd8\xff" * 10
        self._upload_one_file(engine, content=content)

        _, sessions_body = _get(engine.port, "/api/lcloud/v2/restore/sessions")
        session_id = sessions_body["sessions"][0]["sessionId"]
        _, files_body = _get(
            engine.port,
            f"/api/lcloud/v2/restore/files?sessionId={session_id}",
        )
        token = files_body["tokens"]["f1"]

        ctx = _ssl_ctx()
        req = urllib.request.Request(
            f"https://127.0.0.1:{engine.port}/api/lcloud/v2/restore/file"
            f"?sessionId={session_id}&fileId=f1&token={token}"
        )
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            body_bytes = resp.read()
        assert body_bytes == content

    def test_restore_file_401_on_bad_token(self, engine_with_folder):
        engine, _, _ = engine_with_folder
        try:
            ctx = _ssl_ctx()
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

        ctx = _ssl_ctx()
        req = urllib.request.Request(
            f"https://127.0.0.1:{engine.port}/api/lcloud/v2/restore/file"
            f"?sessionId={session_id}&fileId=f1&token={token}"
        )
        urllib.request.urlopen(req, context=ctx, timeout=5).close()

        try:
            urllib.request.urlopen(req, context=ctx, timeout=5)
            assert False, "expected 401 on second use"
        except urllib.error.HTTPError as e:
            assert e.code == 401

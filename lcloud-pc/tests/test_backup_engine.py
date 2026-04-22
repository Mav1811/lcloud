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

        saved = [f for f in backup_folder.rglob("*") if f.is_file()]
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

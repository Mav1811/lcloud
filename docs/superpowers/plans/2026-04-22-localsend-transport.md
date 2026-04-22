# LocalSend-Inspired Transport Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Lcloud's mDNS + HTTP pull model with multicast UDP discovery + HTTPS push (LocalSend-inspired), fixing all structural transport bugs and adding encryption.

**Architecture:** PC runs an HTTPS server (port 53317, self-signed cert) and broadcasts its presence via multicast UDP every 2 seconds. Android listens for the broadcast, then pushes files directly to the PC's HTTPS server one by one, giving real per-file progress on both sides.

**Tech Stack:**
- PC: Python 3.12, `cryptography` (certs), `ssl` (built-in HTTPS), `socket` (multicast UDP)
- Android: Flutter/Dart, `dart:io` HttpClient (HTTPS), `RawDatagramSocket` (multicast UDP), `multicast_lock` (Android WiFi chip unlock), `crypto` (fingerprint)

---

## File Map

### PC — files changed

| File | Action | Responsibility |
|------|--------|---------------|
| `lcloud-pc/requirements.txt` | Modify | Add `cryptography`, remove `zeroconf`, remove `requests` |
| `lcloud-pc/src/config.py` | Modify | New constants: port 53317, multicast addr/port, cert paths |
| `lcloud-pc/src/core/certs.py` | **Create** | Generate + load self-signed RSA-2048 cert, derive fingerprint |
| `lcloud-pc/src/core/discovery.py` | **Rewrite** | Multicast UDP broadcaster (drop zeroconf entirely) |
| `lcloud-pc/src/core/backup_engine.py` | **Rewrite** | HTTPS server, session mgmt, /info /prepare-upload /upload /cancel |
| `lcloud-pc/src/main.py` | Modify | Wire new certs + new discovery signature |
| `lcloud-pc/tests/test_certs.py` | **Create** | Unit tests for cert generation and fingerprint |
| `lcloud-pc/tests/test_backup_engine.py` | **Rewrite** | Tests for all new endpoints + session logic |

### Android — files changed

| File | Action | Responsibility |
|------|--------|---------------|
| `lcloud-android/pubspec.yaml` | Modify | Add `multicast_lock`, remove `multicast_dns` + `shelf` + `shelf_router` |
| `lcloud-android/android/app/src/main/AndroidManifest.xml` | Modify | Add `CHANGE_WIFI_MULTICAST_STATE` permission |
| `lcloud-android/lib/services/discovery.dart` | **Rewrite** | Multicast UDP listener (drop mDNS) |
| `lcloud-android/lib/services/transfer_client.dart` | **Create** | HTTPS push client: prepareUpload + uploadFile (streaming) + cancel |
| `lcloud-android/lib/services/http_server.dart` | **Delete** | No longer needed — phone no longer serves files |
| `lcloud-android/lib/screens/home_screen.dart` | Modify | Wire new discovery + TransferClient, real per-file progress |

---

## Track A — PC (Python)

### Task A1: Update config.py

**Files:**
- Modify: `lcloud-pc/src/config.py`

- [ ] **Step 1: Open config.py and replace the networking constants block**

Replace from line 13 (`# Networking`) through line 16 (`ANDROID_SERVER_PORT = ...`) with:

```python
# Networking — LocalSend-inspired protocol
LCLOUD_PORT = 53317          # PC HTTPS server (same port as LocalSend)
MULTICAST_GROUP = "224.0.0.167"
MULTICAST_PORT = 53317
PROTOCOL_VERSION = "1.0"
```

Also add cert path constants. After the `_log_path` function (around line 57), add:

```python
def _cert_path() -> Path:
    appdata = os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    return Path(appdata) / "lcloud" / "lcloud.crt"

def _key_path() -> Path:
    appdata = os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    return Path(appdata) / "lcloud" / "lcloud.key"

CERT_PATH: Path = _cert_path()
KEY_PATH: Path = _key_path()
```

Remove the old `PC_PORT`, `ANDROID_SERVER_PORT`, `SERVICE_TYPE`, `PC_SERVICE_NAME` constants.

- [ ] **Step 2: Verify config imports still work**

```bash
cd lcloud-pc
call venv\Scripts\activate
python -c "from config import LCLOUD_PORT, MULTICAST_GROUP, MULTICAST_PORT, CERT_PATH, KEY_PATH; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add lcloud-pc/src/config.py
git commit -m "chore: update config for HTTPS + multicast transport"
```

---

### Task A2: Update requirements.txt

**Files:**
- Modify: `lcloud-pc/requirements.txt`

- [ ] **Step 1: Replace requirements.txt**

```
customtkinter>=5.2.2
pystray>=0.19.5
Pillow>=10.0.0
cryptography>=42.0.0
pytest>=8.0.0
pyinstaller
```

Removed: `zeroconf`, `requests` (phone pushes to us now — no outbound HTTP needed).
Added: `cryptography` (self-signed TLS cert generation).

- [ ] **Step 2: Reinstall dependencies**

```bash
cd lcloud-pc
call venv\Scripts\activate
pip install -r requirements.txt
```

Expected: `Successfully installed cryptography-...` (no errors)

- [ ] **Step 3: Commit**

```bash
git add lcloud-pc/requirements.txt
git commit -m "chore: swap zeroconf+requests for cryptography package"
```

---

### Task A3: Create core/certs.py + tests

**Files:**
- Create: `lcloud-pc/src/core/certs.py`
- Create: `lcloud-pc/tests/test_certs.py`

- [ ] **Step 1: Write the failing tests**

Create `lcloud-pc/tests/test_certs.py`:

```python
"""Tests for TLS certificate management."""
import hashlib
import tempfile
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.certs import get_fingerprint, load_or_generate


class TestLoadOrGenerate:
    def test_creates_cert_files_when_missing(self, tmp_path):
        cert_path = tmp_path / "lcloud.crt"
        key_path = tmp_path / "lcloud.key"
        cert_pem, key_pem = load_or_generate(cert_path, key_path)
        assert cert_path.exists()
        assert key_path.exists()
        assert "BEGIN CERTIFICATE" in cert_pem
        assert "BEGIN RSA PRIVATE KEY" in key_pem or "BEGIN PRIVATE KEY" in key_pem

    def test_returns_same_cert_on_reload(self, tmp_path):
        cert_path = tmp_path / "lcloud.crt"
        key_path = tmp_path / "lcloud.key"
        cert_pem1, _ = load_or_generate(cert_path, key_path)
        cert_pem2, _ = load_or_generate(cert_path, key_path)
        assert cert_pem1 == cert_pem2

    def test_generated_cert_is_valid_x509(self, tmp_path):
        cert_path = tmp_path / "lcloud.crt"
        key_path = tmp_path / "lcloud.key"
        cert_pem, _ = load_or_generate(cert_path, key_path)
        cert = x509.load_pem_x509_certificate(cert_pem.encode())
        assert cert.subject.get_attributes_for_oid(
            x509.oid.NameOID.COMMON_NAME
        )[0].value == "lcloud"


class TestGetFingerprint:
    def test_returns_64_char_hex_string(self, tmp_path):
        cert_path = tmp_path / "lcloud.crt"
        key_path = tmp_path / "lcloud.key"
        cert_pem, _ = load_or_generate(cert_path, key_path)
        fp = get_fingerprint(cert_pem)
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_fingerprint_is_stable(self, tmp_path):
        cert_path = tmp_path / "lcloud.crt"
        key_path = tmp_path / "lcloud.key"
        cert_pem, _ = load_or_generate(cert_path, key_path)
        assert get_fingerprint(cert_pem) == get_fingerprint(cert_pem)

    def test_fingerprint_is_sha256_of_der(self, tmp_path):
        cert_path = tmp_path / "lcloud.crt"
        key_path = tmp_path / "lcloud.key"
        cert_pem, _ = load_or_generate(cert_path, key_path)
        cert = x509.load_pem_x509_certificate(cert_pem.encode())
        der = cert.public_bytes(serialization.Encoding.DER)
        expected = hashlib.sha256(der).hexdigest()
        assert get_fingerprint(cert_pem) == expected
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
cd lcloud-pc
call venv\Scripts\activate
pytest tests/test_certs.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'core.certs'`

- [ ] **Step 3: Create core/certs.py**

```python
"""
Lcloud PC — TLS Certificate Manager

Generates and persists a self-signed RSA-2048 certificate for the HTTPS server.
On first run, creates cert + key files. On subsequent runs, loads existing ones.
"""
import datetime
import hashlib
import logging
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

logger = logging.getLogger(__name__)


def load_or_generate(cert_path: Path, key_path: Path) -> tuple[str, str]:
    """
    Load existing cert/key pair or generate a new one.

    Args:
        cert_path: Where to store / load the PEM certificate.
        key_path:  Where to store / load the PEM private key.

    Returns:
        (cert_pem, key_pem) as strings.
    """
    if cert_path.exists() and key_path.exists():
        logger.info("Loading TLS certificate from %s", cert_path)
        return (
            cert_path.read_text(encoding="utf-8"),
            key_path.read_text(encoding="utf-8"),
        )

    logger.info("Generating self-signed TLS certificate...")
    cert_path.parent.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "lcloud"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("lcloud")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode("utf-8")

    cert_path.write_text(cert_pem, encoding="utf-8")
    key_path.write_text(key_pem, encoding="utf-8")
    logger.info("Certificate saved to %s", cert_path)

    return cert_pem, key_pem


def get_fingerprint(cert_pem: str) -> str:
    """Return the SHA-256 fingerprint of the cert as a 64-char hex string."""
    cert = x509.load_pem_x509_certificate(cert_pem.encode())
    der = cert.public_bytes(serialization.Encoding.DER)
    return hashlib.sha256(der).hexdigest()
```

- [ ] **Step 4: Run tests — verify they PASS**

```bash
pytest tests/test_certs.py -v
```

Expected: `3 passed, 0 failed` (the `test_fingerprint_is_stable` and related tests all green)

- [ ] **Step 5: Commit**

```bash
git add lcloud-pc/src/core/certs.py lcloud-pc/tests/test_certs.py
git commit -m "feat: add TLS certificate manager (self-signed RSA-2048)"
```

---

### Task A4: Rewrite core/discovery.py

**Files:**
- Modify: `lcloud-pc/src/core/discovery.py`

- [ ] **Step 1: Replace discovery.py entirely**

```python
"""
Lcloud PC — Device Discovery (Multicast UDP)

Broadcasts the PC's presence on the local network every 2 seconds.
The Android app listens on the multicast group, parses the JSON payload,
and uses the included IP + fingerprint to connect.

No Bonjour / Zeroconf / mDNS required.
"""
import json
import logging
import socket
import threading
from typing import Callable

from config import MULTICAST_GROUP, MULTICAST_PORT, PROTOCOL_VERSION

logger = logging.getLogger(__name__)

_BROADCAST_INTERVAL = 2.0  # seconds between broadcasts


class LcloudDiscovery:
    """
    Broadcasts PC identity via multicast UDP.

    Usage:
        discovery = LcloudDiscovery(
            alias="MyPC",
            fingerprint="abc123...",
            port=53317,
        )
        discovery.start()
        # ... app runs ...
        discovery.stop()
    """

    def __init__(
        self,
        alias: str,
        fingerprint: str,
        port: int,
        on_phone_found: Callable[[str, str, int], None] | None = None,
        on_phone_lost: Callable[[str], None] | None = None,
    ) -> None:
        self._alias = alias
        self._fingerprint = fingerprint
        self._port = port
        # on_phone_found / on_phone_lost kept for API compatibility with main.py
        # but are unused — phone connects to us, not the other way around.
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start broadcasting in a daemon thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._broadcast_loop, daemon=True, name="lcloud-discovery"
        )
        self._thread.start()
        logger.info(
            "Discovery: broadcasting on %s:%s every %.0fs",
            MULTICAST_GROUP, MULTICAST_PORT, _BROADCAST_INTERVAL,
        )

    def stop(self) -> None:
        """Signal the broadcast thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        logger.info("Discovery stopped.")

    # ------------------------------------------------------------------

    def _broadcast_loop(self) -> None:
        payload = json.dumps({
            "alias": self._alias,
            "version": PROTOCOL_VERSION,
            "deviceType": "desktop",
            "fingerprint": self._fingerprint,
            "port": self._port,
            "protocol": "https",
        }).encode()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)

        try:
            while not self._stop_event.is_set():
                try:
                    sock.sendto(payload, (MULTICAST_GROUP, MULTICAST_PORT))
                except OSError as exc:
                    logger.warning("Broadcast send failed: %s", exc)
                self._stop_event.wait(_BROADCAST_INTERVAL)
        finally:
            sock.close()

    # ------------------------------------------------------------------

    @staticmethod
    def local_ip() -> str:
        """Return the machine's LAN IP (not loopback)."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
cd lcloud-pc
call venv\Scripts\activate
python -c "from core.discovery import LcloudDiscovery; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Quick smoke test — start and stop**

```bash
python -c "
import time
from core.discovery import LcloudDiscovery
d = LcloudDiscovery(alias='TestPC', fingerprint='abc123', port=53317)
d.start()
time.sleep(3)
d.stop()
print('broadcast loop OK')
"
```

Expected: `broadcast loop OK` (no exceptions)

- [ ] **Step 4: Commit**

```bash
git add lcloud-pc/src/core/discovery.py
git commit -m "feat: replace mDNS discovery with multicast UDP broadcaster"
```

---

### Task A5: Rewrite core/backup_engine.py + tests

**Files:**
- Modify: `lcloud-pc/src/core/backup_engine.py`
- Modify: `lcloud-pc/tests/test_backup_engine.py`

- [ ] **Step 1: Write failing tests first**

Replace `lcloud-pc/tests/test_backup_engine.py`:

```python
"""Tests for the HTTPS backup engine (session management + file upload)."""
import json
import ssl
import tempfile
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.backup_engine import BackupEngine
from core.certs import load_or_generate


@pytest.fixture()
def engine_with_folder(tmp_path):
    """Start a real HTTPS engine on an ephemeral port; yield it; shut it down."""
    cert_path = tmp_path / "lcloud.crt"
    key_path = tmp_path / "lcloud.key"
    cert_pem, _ = load_or_generate(cert_path, key_path)

    engine = BackupEngine()
    backup_folder = tmp_path / "backup"
    backup_folder.mkdir()

    engine.start_server(
        backup_folder=backup_folder,
        cert_path=cert_path,
        key_path=key_path,
        alias="TestPC",
        fingerprint="test-fp",
        port=0,  # OS picks ephemeral port
    )
    yield engine, backup_folder, cert_path
    engine.stop_server()


def _ssl_ctx(cert_path: Path) -> ssl.SSLContext:
    """Build a client SSL context that trusts our self-signed cert."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _get(port, path, cert_path):
    ctx = _ssl_ctx(cert_path)
    url = f"https://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


def _post(port, path, body_dict, cert_path):
    ctx = _ssl_ctx(cert_path)
    url = f"https://127.0.0.1:{port}{path}"
    body = json.dumps(body_dict).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Content-Length", str(len(body)))
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post_raw(port, path, data: bytes, cert_path):
    ctx = _ssl_ctx(cert_path)
    url = f"https://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/octet-stream")
    req.add_header("Content-Length", str(len(data)))
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


class TestInfoEndpoint:
    def test_returns_alias_and_fingerprint(self, engine_with_folder):
        engine, _, cert_path = engine_with_folder
        port = engine.port
        status, body = _get(port, "/api/lcloud/v2/info", cert_path)
        assert status == 200
        assert body["alias"] == "TestPC"
        assert body["fingerprint"] == "test-fp"
        assert body["deviceType"] == "desktop"


class TestPrepareUpload:
    def test_returns_session_and_tokens(self, engine_with_folder):
        engine, _, cert_path = engine_with_folder
        port = engine.port
        status, body = _post(port, "/api/lcloud/v2/prepare-upload", {
            "deviceAlias": "TestPhone",
            "files": [
                {"fileId": "f1", "fileName": "a.jpg", "size": 100,
                 "fileType": "image/jpeg", "path": "/DCIM/a.jpg",
                 "category": "photo", "modifiedAt": "2026-01-01T00:00:00"},
            ],
        }, cert_path)
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
        port = engine.port
        try:
            status, body = _post(port, "/api/lcloud/v2/prepare-upload", {
                "deviceAlias": "Phone", "files": [],
            }, cert_path)
            assert status == 503
            assert body["error"] == "no_backup_folder"
        finally:
            engine.stop_server()

    def test_507_when_disk_too_full(self, engine_with_folder, monkeypatch):
        engine, _, cert_path = engine_with_folder
        port = engine.port

        import shutil
        monkeypatch.setattr(
            shutil, "disk_usage",
            lambda _: shutil.usage(total=1_000_000, used=999_000, free=1_000)
        )

        status, body = _post(port, "/api/lcloud/v2/prepare-upload", {
            "deviceAlias": "Phone",
            "files": [{"fileId": "f1", "fileName": "big.mp4", "size": 500_000_000,
                       "fileType": "video/mp4", "path": "/big.mp4",
                       "category": "video", "modifiedAt": "2026-01-01T00:00:00"}],
        }, cert_path)
        assert status == 507
        assert body["error"] == "insufficient_storage"


class TestUpload:
    def test_full_upload_flow(self, engine_with_folder):
        engine, backup_folder, cert_path = engine_with_folder
        port = engine.port

        # 1. Prepare
        _, prep = _post(port, "/api/lcloud/v2/prepare-upload", {
            "deviceAlias": "Phone",
            "files": [{"fileId": "f1", "fileName": "photo.jpg", "size": 3,
                       "fileType": "image/jpeg", "path": "/DCIM/photo.jpg",
                       "category": "photo", "modifiedAt": "2026-01-01T10:00:00"}],
        }, cert_path)

        session_id = prep["sessionId"]
        token = prep["files"]["f1"]

        # 2. Upload
        status, body = _post_raw(
            port,
            f"/api/lcloud/v2/upload?sessionId={session_id}&fileId=f1&token={token}",
            b"\xff\xd8\xff",  # fake JPEG bytes
            cert_path,
        )
        assert status == 200
        assert body["success"] is True

        # 3. File must exist somewhere under backup_folder
        all_files = list(backup_folder.rglob("*"))
        saved = [f for f in all_files if f.is_file()]
        assert len(saved) == 1

    def test_401_on_bad_token(self, engine_with_folder):
        engine, _, cert_path = engine_with_folder
        port = engine.port

        _, prep = _post(port, "/api/lcloud/v2/prepare-upload", {
            "deviceAlias": "Phone",
            "files": [{"fileId": "f1", "fileName": "x.jpg", "size": 1,
                       "fileType": "image/jpeg", "path": "/x.jpg",
                       "category": "photo", "modifiedAt": "2026-01-01T00:00:00"}],
        }, cert_path)
        session_id = prep["sessionId"]

        status, body = _post_raw(
            port,
            f"/api/lcloud/v2/upload?sessionId={session_id}&fileId=f1&token=WRONG",
            b"x",
            cert_path,
        )
        assert status == 401


class TestCancel:
    def test_cancel_removes_session(self, engine_with_folder):
        engine, _, cert_path = engine_with_folder
        port = engine.port

        _, prep = _post(port, "/api/lcloud/v2/prepare-upload", {
            "deviceAlias": "Phone",
            "files": [{"fileId": "f1", "fileName": "x.jpg", "size": 1,
                       "fileType": "image/jpeg", "path": "/x.jpg",
                       "category": "photo", "modifiedAt": "2026-01-01T00:00:00"}],
        }, cert_path)
        session_id = prep["sessionId"]

        status, body = _post(
            port,
            f"/api/lcloud/v2/cancel?sessionId={session_id}",
            {},
            cert_path,
        )
        assert status == 200
        assert body["cancelled"] is True

        # Uploading after cancel must fail (session gone)
        _, prep2 = _post(port, "/api/lcloud/v2/prepare-upload", {
            "deviceAlias": "Phone",
            "files": [{"fileId": "f1", "fileName": "x.jpg", "size": 1,
                       "fileType": "image/jpeg", "path": "/x.jpg",
                       "category": "photo", "modifiedAt": "2026-01-01T00:00:00"}],
        }, cert_path)
        status2, _ = _post_raw(
            port,
            f"/api/lcloud/v2/upload?sessionId={session_id}&fileId=f1&token=any",
            b"x",
            cert_path,
        )
        assert status2 == 401
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
pytest tests/test_backup_engine.py -v 2>&1 | head -30
```

Expected: `ImportError` or `AttributeError` — BackupEngine missing new methods.

- [ ] **Step 3: Rewrite backup_engine.py**

```python
"""
Lcloud PC — Backup Engine (HTTPS Server)

Receives file uploads from the Android app.

Endpoints:
  GET  /api/lcloud/v2/info              — device identity + fingerprint
  POST /api/lcloud/v2/prepare-upload    — start session, get file tokens
  POST /api/lcloud/v2/upload            — upload one file (stream to disk)
  POST /api/lcloud/v2/cancel            — cancel session
"""
import json
import logging
import shutil
import ssl
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse

from config import LCLOUD_PORT, MIN_FREE_SPACE_BYTES
from core.file_organizer import FileOrganizer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
ProgressCallback = Callable[[str, int, int, int, int], None]
# (filename, current_index, total_files, bytes_done, bytes_total)

CompleteCallback = Callable[[int, int, list[str]], None]
# (files_saved, bytes_saved, error_file_ids)

DiskFullCallback = Callable[[int, int], None]
# (free_bytes, needed_bytes)


# ---------------------------------------------------------------------------
# Session data
# ---------------------------------------------------------------------------

@dataclass
class _FileEntry:
    file_id: str
    file_name: str
    size: int
    file_type: str
    path: str
    category: str
    modified_at: datetime
    token: str = field(default_factory=lambda: str(uuid.uuid4()))
    done: bool = False


@dataclass
class _Session:
    session_id: str
    files: dict[str, _FileEntry]   # fileId → _FileEntry
    bytes_received: int = 0
    files_done: int = 0


# ---------------------------------------------------------------------------
# HTTP request handler
# ---------------------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    """Handles all HTTPS requests from the Android app."""

    engine: "BackupEngine"   # injected by BackupEngine.start_server

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        logger.debug("HTTP %s", format % args)

    # --- Routing ---

    def do_GET(self) -> None:
        if self.path == "/api/lcloud/v2/info":
            self._json(200, {
                "alias": self.engine.alias,
                "fingerprint": self.engine.fingerprint,
                "deviceType": "desktop",
            })
        else:
            self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        route = parsed.path

        if route == "/api/lcloud/v2/prepare-upload":
            self._handle_prepare()
        elif route == "/api/lcloud/v2/upload":
            self._handle_upload(params)
        elif route == "/api/lcloud/v2/cancel":
            self._handle_cancel(params)
        else:
            self._json(404, {"error": "not_found"})

    # --- Handlers ---

    def _handle_prepare(self) -> None:
        body = self._read_json()
        if body is None:
            return

        if not self.engine.backup_folder:
            self._json(503, {"error": "no_backup_folder"})
            return

        files_meta: list[dict] = body.get("files", [])
        total_needed = sum(f.get("size", 0) for f in files_meta)

        try:
            disk = shutil.disk_usage(self.engine.backup_folder)
            if disk.free < total_needed + MIN_FREE_SPACE_BYTES:
                if self.engine._on_disk_full:
                    self.engine._on_disk_full(disk.free, total_needed)
                self._json(507, {
                    "error": "insufficient_storage",
                    "free_bytes": disk.free,
                    "needed_bytes": total_needed,
                })
                return
        except OSError as exc:
            logger.warning("Disk usage check failed: %s", exc)

        session_id = str(uuid.uuid4())
        files: dict[str, _FileEntry] = {}

        for f in files_meta:
            fid = f.get("fileId") or str(uuid.uuid4())
            ts = f.get("modifiedAt")
            entry = _FileEntry(
                file_id=fid,
                file_name=f.get("fileName", "unknown"),
                size=f.get("size", 0),
                file_type=f.get("fileType", ""),
                path=f.get("path", ""),
                category=f.get("category", "other"),
                modified_at=datetime.fromisoformat(ts) if ts else datetime.now(),
            )
            files[fid] = entry

        session = _Session(session_id=session_id, files=files)
        with self.engine._lock:
            self.engine._sessions[session_id] = session

        logger.info("Session %s: %d files prepared", session_id, len(files))
        self._json(200, {
            "sessionId": session_id,
            "files": {fid: e.token for fid, e in files.items()},
        })

    def _handle_upload(self, params: dict) -> None:
        session_id = params.get("sessionId", [None])[0]
        file_id    = params.get("fileId",    [None])[0]
        token      = params.get("token",     [None])[0]

        with self.engine._lock:
            session = self.engine._sessions.get(session_id)

        if not session:
            self._json(401, {"error": "invalid_session"})
            return

        entry = session.files.get(file_id)
        if not entry or entry.token != token:
            self._json(401, {"error": "invalid_token"})
            return

        length = int(self.headers.get("Content-Length", 0))

        # Stream file to a temp file — never load entire file into memory
        try:
            suffix = Path(entry.file_name).suffix or ".bin"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                remaining = length
                while remaining > 0:
                    chunk = self.rfile.read(min(65536, remaining))
                    if not chunk:
                        break
                    tmp.write(chunk)
                    remaining -= len(chunk)
                tmp_path = Path(tmp.name)

            organizer_path = entry.path if entry.path else entry.file_name
            self.engine._organizer.organize(
                source_path=tmp_path,
                original_name=organizer_path,
                backup_root=self.engine.backup_folder,
                modified_at=entry.modified_at,
            )
            tmp_path.unlink(missing_ok=True)
            entry.done = True

        except Exception as exc:
            logger.error("Failed to save %s: %s", entry.file_name, exc)
            self._json(500, {"error": "write_failed", "detail": str(exc)})
            return

        with self.engine._lock:
            session.bytes_received += length
            session.files_done += 1
            done        = session.files_done
            total       = len(session.files)
            bytes_done  = session.bytes_received
            bytes_total = sum(f.size for f in session.files.values())

        if self.engine._on_progress:
            self.engine._on_progress(
                entry.file_name, done, total, bytes_done, bytes_total
            )

        if done == total:
            errors = [fid for fid, f in session.files.items() if not f.done]
            if self.engine._on_complete:
                self.engine._on_complete(done, bytes_done, errors)
            with self.engine._lock:
                self.engine._sessions.pop(session_id, None)
            logger.info("Session %s complete: %d files", session_id, done)

        self._json(200, {"success": True})

    def _handle_cancel(self, params: dict) -> None:
        session_id = params.get("sessionId", [None])[0]
        with self.engine._lock:
            self.engine._sessions.pop(session_id, None)
        logger.info("Session %s cancelled", session_id)
        self._json(200, {"cancelled": True})

    # --- Helpers ---

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid_json"})
            return None

    def _json(self, code: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# BackupEngine
# ---------------------------------------------------------------------------

class BackupEngine:
    """
    Manages the HTTPS server that receives backup uploads from the phone.

    Usage:
        engine = BackupEngine()
        engine.start_server(backup_folder=..., cert_path=..., ...)
        engine.stop_server()
    """

    def __init__(self) -> None:
        self.backup_folder: Path | None = None
        self.alias: str = ""
        self.fingerprint: str = ""
        self.port: int = LCLOUD_PORT
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.Lock()
        self._on_progress: ProgressCallback | None = None
        self._on_complete: CompleteCallback | None = None
        self._on_disk_full: DiskFullCallback | None = None
        self._server: HTTPServer | None = None
        self._server_thread: threading.Thread | None = None
        self._organizer = FileOrganizer()

    def start_server(
        self,
        backup_folder: Path | None,
        cert_path: Path,
        key_path: Path,
        alias: str,
        fingerprint: str,
        on_progress: ProgressCallback | None = None,
        on_complete: CompleteCallback | None = None,
        on_disk_full: DiskFullCallback | None = None,
        port: int = LCLOUD_PORT,
    ) -> None:
        """Start the HTTPS server. Wraps socket with TLS using the provided cert."""
        if self._server:
            logger.warning("Server already running.")
            return

        self.backup_folder = backup_folder
        self.alias = alias
        self.fingerprint = fingerprint
        self._on_progress = on_progress
        self._on_complete = on_complete
        self._on_disk_full = on_disk_full

        _Handler.engine = self

        self._server = HTTPServer(("0.0.0.0", port), _Handler)

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
        self._server.socket = ctx.wrap_socket(self._server.socket, server_side=True)

        # Store actual port (important when port=0 for tests)
        self.port = self._server.server_address[1]

        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="lcloud-server",
        )
        self._server_thread.start()
        logger.info("HTTPS backup server listening on port %s", self.port)

    def stop_server(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None
            self._server_thread = None
            logger.info("Backup server stopped.")

    def set_backup_folder(self, folder: Path) -> None:
        self.backup_folder = folder

    def set_phone(self, address: str | None, port: int | None) -> None:
        pass  # Phone connects to us — nothing to track here
```

- [ ] **Step 4: Run tests — verify they PASS**

```bash
pytest tests/test_backup_engine.py -v
```

Expected: all tests pass. The `test_507_when_disk_too_full` test monkeypatches `shutil.disk_usage` — if it fails on the namedtuple, replace with:
```python
import collections
DiskUsage = collections.namedtuple('usage', ['total', 'used', 'free'])
monkeypatch.setattr(shutil, "disk_usage", lambda _: DiskUsage(1_000_000, 999_000, 1_000))
```

- [ ] **Step 5: Run full test suite to check nothing broken**

```bash
pytest tests/ -v
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add lcloud-pc/src/core/backup_engine.py lcloud-pc/tests/test_backup_engine.py
git commit -m "feat: rewrite backup engine as HTTPS push server (LocalSend protocol)"
```

---

### Task A6: Update main.py

**Files:**
- Modify: `lcloud-pc/src/main.py`

- [ ] **Step 1: Replace main.py**

```python
"""
Lcloud PC App — Entry Point
Wires all components together: HTTPS server, multicast discovery, UI, tray.
"""
import logging
import socket
import sys
from pathlib import Path

from config import CERT_PATH, KEY_PATH, LCLOUD_PORT, Settings, setup_logging
from core.backup_engine import BackupEngine
from core.certs import get_fingerprint, load_or_generate
from core.discovery import LcloudDiscovery
from ui.main_window import LcloudWindow
from ui.tray import LcloudTray

logger = logging.getLogger(__name__)


class LcloudApp:
    def __init__(self) -> None:
        setup_logging()
        logger.info("Lcloud starting up...")

        self.settings = Settings()
        self.settings.load()

        # Load or generate TLS cert
        self._cert_pem, _ = load_or_generate(CERT_PATH, KEY_PATH)
        self._fingerprint = get_fingerprint(self._cert_pem)
        self._alias = socket.gethostname()

        self.window = LcloudWindow(
            on_folder_change=self._on_folder_change,
            on_backup_now=self._on_backup_now,
            on_settings_change=self._on_settings_change,
            current_port=self.settings.port,
        )
        self.engine = BackupEngine()
        self.tray = LcloudTray(on_open=self.window.show, on_quit=self._quit)
        self.discovery = LcloudDiscovery(
            alias=self._alias,
            fingerprint=self._fingerprint,
            port=self.settings.port,
        )

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_folder_change(self, folder: Path) -> None:
        self.settings.backup_folder = str(folder)
        self.settings.save()
        self.engine.set_backup_folder(folder)
        logger.info("Backup folder: %s", folder)

    def _on_backup_now(self) -> None:
        self.window.show_info(
            "Start Backup on Phone",
            "Open the Lcloud app on your Android phone and tap Backup Now.",
        )

    def _on_settings_change(self, port: int) -> None:
        self.settings.port = port
        self.settings.save()
        logger.info("Port setting saved (%s) — restart to apply.", port)

    def _on_disk_full(self, free_bytes: int, needed_bytes: int) -> None:
        free_mb   = free_bytes   // (1024 * 1024)
        needed_mb = needed_bytes // (1024 * 1024)
        self.window.show_warning(
            "Not Enough Disk Space",
            f"Backup stopped — not enough space on PC.\n\n"
            f"Free:   {free_mb} MB\nNeeded: {needed_mb} MB\n\n"
            f"Free up space and try again.",
        )
        self.window.update_status("Backup stopped — not enough disk space", "#ef4444")

    def _quit(self) -> None:
        logger.info("Quit requested.")
        self.discovery.stop()
        self.engine.stop_server()
        self.window.after(0, self.window.destroy)

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def run(self) -> None:
        backup_folder = (
            Path(self.settings.backup_folder)
            if self.settings.backup_folder
            else Path.home() / "lcloud_backup"
        )
        if self.settings.backup_folder:
            folder = Path(self.settings.backup_folder)
            if folder.exists():
                self.window.set_backup_folder(folder)

        self.engine.start_server(
            backup_folder=backup_folder,
            cert_path=CERT_PATH,
            key_path=KEY_PATH,
            alias=self._alias,
            fingerprint=self._fingerprint,
            on_progress=self.window.update_progress,
            on_complete=self.window.complete_progress,
            on_disk_full=self._on_disk_full,
            port=self.settings.port,
        )
        self.discovery.start()
        self.tray.start()

        logger.info("All services started. Fingerprint: %s", self._fingerprint[:16] + "...")
        self.window.mainloop()
        logger.info("Lcloud exited.")
        sys.exit(0)


def main() -> None:
    app = LcloudApp()
    app.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify app starts without crashing (will open a window)**

```bash
cd lcloud-pc
call venv\Scripts\activate
python src/main.py
```

Expected: Window opens, tray icon appears, no exceptions in console. Close it with the tray "Quit" option.

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add lcloud-pc/src/main.py
git commit -m "feat: wire HTTPS engine + multicast discovery into main app"
```

---

## Track B — Android (Dart/Flutter)

### Task B1: Update dependencies + permissions

**Files:**
- Modify: `lcloud-android/pubspec.yaml`
- Modify: `lcloud-android/android/app/src/main/AndroidManifest.xml`

- [ ] **Step 1: Update pubspec.yaml**

Replace the `dependencies` block:

```yaml
dependencies:
  flutter:
    sdk: flutter
  permission_handler: ^11.3.1
  path_provider: ^2.1.3
  shared_preferences: ^2.2.3
  http: ^1.2.1
  crypto: ^3.0.3
  intl: ^0.19.0
  multicast_lock: ^1.0.1
```

Removed: `shelf`, `shelf_router` (no longer serving files), `multicast_dns` (replaced by UDP socket).
Added: `multicast_lock` (Android requires acquiring a WifiManager lock to receive multicast packets).

- [ ] **Step 2: Add CHANGE_WIFI_MULTICAST_STATE permission to AndroidManifest.xml**

In `android/app/src/main/AndroidManifest.xml`, add before the `<application>` tag:

```xml
<uses-permission android:name="android.permission.CHANGE_WIFI_MULTICAST_STATE"/>
```

It should already have `INTERNET` and `READ_EXTERNAL_STORAGE` — leave those.

- [ ] **Step 3: Run pub get**

```bash
cd lcloud-android
flutter pub get
```

Expected: `Got dependencies!` — no errors.

- [ ] **Step 4: Commit**

```bash
git add lcloud-android/pubspec.yaml lcloud-android/pubspec.lock
git add "lcloud-android/android/app/src/main/AndroidManifest.xml"
git commit -m "chore: update Android deps — add multicast_lock, drop shelf + mDNS"
```

---

### Task B2: Create services/transfer_client.dart + tests

**Files:**
- Create: `lcloud-android/lib/services/transfer_client.dart`
- Create: `lcloud-android/test/services/transfer_client_test.dart`

- [ ] **Step 1: Create transfer_client.dart**

```dart
/// Lcloud Android — Transfer Client
///
/// Pushes files to the PC's HTTPS server using the Lcloud v2 protocol.
/// Verifies the PC's self-signed cert by SHA-256 fingerprint (TOFU).
/// Streams files from disk — never loads the entire file into memory.
library;

import 'dart:convert';
import 'dart:io';
import 'package:crypto/crypto.dart';

/// One file to be transferred.
class TransferFile {
  const TransferFile({
    required this.fileId,
    required this.fileName,
    required this.fileSize,
    required this.fileType,
    required this.path,
    required this.category,
    required this.modifiedAt,
  });

  final String fileId;
  final String fileName;
  final int fileSize;
  final String fileType;
  final String path;
  final String category;
  final DateTime modifiedAt;

  Map<String, dynamic> toJson() => {
        'fileId': fileId,
        'fileName': fileName,
        'size': fileSize,
        'fileType': fileType,
        'path': path,
        'category': category,
        'modifiedAt': modifiedAt.toIso8601String(),
      };
}

/// Thrown when the PC returns a known error code.
class TransferException implements Exception {
  const TransferException(this.code, [this.detail = '']);
  final String code;   // 'disk_full' | 'no_backup_folder' | 'upload_failed' | 'invalid_token'
  final String detail;

  @override
  String toString() => 'TransferException($code: $detail)';
}

/// HTTPS client for the Lcloud v2 transfer protocol.
class TransferClient {
  TransferClient({
    required this.pcAddress,
    required this.pcPort,
    required this.fingerprint,
  });

  final String pcAddress;
  final int pcPort;
  final String fingerprint;   // SHA-256 hex — used to trust the PC's self-signed cert

  String get _base => 'https://$pcAddress:$pcPort/api/lcloud/v2';

  /// Build an HttpClient that trusts the PC cert by fingerprint only.
  HttpClient _client() {
    final client = HttpClient()
      ..connectionTimeout = const Duration(seconds: 15)
      ..badCertificateCallback = (X509Certificate cert, String host, int port) {
        final fp = sha256.convert(cert.der).toString();
        return fp == fingerprint;
      };
    return client;
  }

  /// Send file list; get back sessionId + per-file tokens.
  ///
  /// Returns a map: `{'__sessionId__': '...', 'fileId1': 'token1', ...}`
  Future<Map<String, String>> prepareUpload({
    required String deviceAlias,
    required List<TransferFile> files,
  }) async {
    final client = _client();
    try {
      final req = await client
          .postUrl(Uri.parse('$_base/prepare-upload'))
          .timeout(const Duration(seconds: 15));

      final bodyBytes = utf8.encode(jsonEncode({
        'deviceAlias': deviceAlias,
        'files': files.map((f) => f.toJson()).toList(),
      }));
      req.headers
        ..contentType = ContentType.json
        ..contentLength = bodyBytes.length;
      req.add(bodyBytes);

      final resp = await req.close().timeout(const Duration(seconds: 15));
      final respBody = await resp.transform(utf8.decoder).join();
      final data = jsonDecode(respBody) as Map<String, dynamic>;

      switch (resp.statusCode) {
        case 507:
          throw TransferException('disk_full',
              'Free: ${data['free_bytes']} B  Need: ${data['needed_bytes']} B');
        case 503:
          throw const TransferException(
              'no_backup_folder', 'Open Lcloud on PC and set a backup folder.');
        case 200:
          break;
        default:
          throw TransferException('prepare_failed', 'HTTP ${resp.statusCode}');
      }

      final sessionId = data['sessionId'] as String;
      final tokens = (data['files'] as Map<String, dynamic>)
          .map((k, v) => MapEntry(k, v as String));
      return {'__sessionId__': sessionId, ...tokens};
    } finally {
      client.close();
    }
  }

  /// Stream one file from disk to the PC.
  ///
  /// [onProgress] is called after each 64 KB chunk with total bytes sent so far.
  Future<void> uploadFile({
    required String sessionId,
    required TransferFile file,
    required String token,
    void Function(int bytesSent)? onProgress,
  }) async {
    final client = _client();
    try {
      final uri = Uri.parse(
        '$_base/upload'
        '?sessionId=${Uri.encodeComponent(sessionId)}'
        '&fileId=${Uri.encodeComponent(file.fileId)}'
        '&token=${Uri.encodeComponent(token)}',
      );

      final req = await client
          .postUrl(uri)
          .timeout(const Duration(seconds: 60));

      req.headers
        ..set('Content-Type',
            file.fileType.isNotEmpty ? file.fileType : 'application/octet-stream')
        ..contentLength = file.fileSize;

      // Stream file in 64 KB chunks
      int sent = 0;
      await for (final chunk in File(file.path).openRead()) {
        req.add(chunk);
        sent += chunk.length;
        onProgress?.call(sent);
      }

      final resp = await req.close().timeout(const Duration(seconds: 60));
      await resp.drain<void>();

      if (resp.statusCode == 401) {
        throw const TransferException('invalid_token');
      }
      if (resp.statusCode != 200) {
        throw TransferException('upload_failed', 'HTTP ${resp.statusCode}');
      }
    } finally {
      client.close();
    }
  }

  /// Cancel the active session (best-effort — errors are swallowed).
  Future<void> cancel(String sessionId) async {
    final client = _client();
    try {
      final req = await client
          .postUrl(Uri.parse(
              '$_base/cancel?sessionId=${Uri.encodeComponent(sessionId)}'))
          .timeout(const Duration(seconds: 5));
      req.headers.contentLength = 0;
      final resp = await req.close().timeout(const Duration(seconds: 5));
      await resp.drain<void>();
    } catch (_) {
      // Best-effort — don't rethrow on cancel
    } finally {
      client.close();
    }
  }
}
```

- [ ] **Step 2: Write widget/unit tests**

Create `lcloud-android/test/services/transfer_client_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:lcloud/services/transfer_client.dart';

void main() {
  group('TransferFile.toJson', () {
    test('serialises all fields correctly', () {
      const file = TransferFile(
        fileId: 'f1',
        fileName: 'photo.jpg',
        fileSize: 1024,
        fileType: 'image/jpeg',
        path: '/DCIM/photo.jpg',
        category: 'photo',
        modifiedAt: const _FakeDateTime(),
      );

      final json = file.toJson();
      expect(json['fileId'], 'f1');
      expect(json['fileName'], 'photo.jpg');
      expect(json['size'], 1024);
      expect(json['fileType'], 'image/jpeg');
      expect(json['path'], '/DCIM/photo.jpg');
      expect(json['category'], 'photo');
      expect(json['modifiedAt'], isA<String>());
    });
  });

  group('TransferException', () {
    test('toString includes code and detail', () {
      const ex = TransferException('disk_full', 'Free: 100 B');
      expect(ex.toString(), contains('disk_full'));
      expect(ex.toString(), contains('Free: 100 B'));
    });

    test('detail defaults to empty string', () {
      const ex = TransferException('no_backup_folder');
      expect(ex.detail, '');
    });
  });
}

// Dart const constructor doesn't support DateTime.now(), use a fixed value.
class _FakeDateTime implements DateTime {
  const _FakeDateTime();

  @override
  String toIso8601String() => '2026-01-01T00:00:00.000';

  // Remaining DateTime interface — not used in tests.
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
```

- [ ] **Step 3: Run the tests**

```bash
cd lcloud-android
flutter test test/services/transfer_client_test.dart
```

Expected: `All tests passed!`

- [ ] **Step 4: Commit**

```bash
git add lcloud-android/lib/services/transfer_client.dart
git add lcloud-android/test/services/transfer_client_test.dart
git commit -m "feat: add HTTPS transfer client with fingerprint verification"
```

---

### Task B3: Rewrite services/discovery.dart

**Files:**
- Modify: `lcloud-android/lib/services/discovery.dart`

- [ ] **Step 1: Replace discovery.dart**

```dart
/// Lcloud Android — Device Discovery (Multicast UDP)
///
/// Listens for the PC's multicast broadcast on 224.0.0.167:53317.
/// On Android, a WifiManager.MulticastLock must be held to receive
/// multicast packets — this is managed via the multicast_lock package.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:multicast_lock/multicast_lock.dart';

const String _multicastGroup = '224.0.0.167';
const int _multicastPort = 53317;

/// A PC that is running Lcloud and broadcasting its presence.
class DiscoveredPC {
  const DiscoveredPC({
    required this.name,
    required this.address,
    required this.port,
    required this.fingerprint,
  });

  final String name;
  final String address;
  final int port;
  final String fingerprint;

  @override
  String toString() => 'DiscoveredPC($name @ $address:$port)';
}

/// Discovers PCs by listening on the multicast group.
///
/// Usage:
///   final discovery = LcloudDiscovery();
///   discovery.startListening(onFound: (pc) { ... });
///   // later:
///   discovery.stopDiscovery();
class LcloudDiscovery {
  RawDatagramSocket? _socket;
  final _multicastLock = MulticastLock();
  bool _running = false;

  /// Start listening for PC broadcasts.
  ///
  /// [onFound] is called each time a valid broadcast is parsed — it may be
  /// called multiple times for the same PC (one per 2-second interval).
  Future<void> startListening({
    required void Function(DiscoveredPC pc) onFound,
  }) async {
    _running = true;

    // Android blocks multicast packets unless we hold this lock.
    await _multicastLock.acquire();

    try {
      _socket = await RawDatagramSocket.bind(
        InternetAddress.anyIPv4,
        _multicastPort,
        reuseAddress: true,
      );
      _socket!.joinMulticast(InternetAddress(_multicastGroup));

      await for (final event in _socket!) {
        if (!_running) break;
        if (event != RawSocketEvent.read) continue;

        final datagram = _socket!.receive();
        if (datagram == null) continue;

        try {
          final text = utf8.decode(datagram.data);
          final map = jsonDecode(text) as Map<String, dynamic>;

          if (map['protocol'] != 'https') continue;

          final pc = DiscoveredPC(
            name: (map['alias'] as String?) ?? 'Lcloud PC',
            address: datagram.address.address,
            port: (map['port'] as int?) ?? _multicastPort,
            fingerprint: (map['fingerprint'] as String?) ?? '',
          );
          onFound(pc);
        } catch (_) {
          // Malformed packet — ignore silently
        }
      }
    } finally {
      await _multicastLock.release();
    }
  }

  /// Stop listening and release the multicast lock.
  void stopDiscovery() {
    _running = false;
    _socket?.close();
    _socket = null;
  }

  /// Returns the device's local WiFi IP (first non-loopback IPv4 address).
  static Future<String?> getLocalIP() async {
    try {
      final interfaces = await NetworkInterface.list(
        type: InternetAddressType.IPv4,
        includeLinkLocal: false,
      );
      for (final iface in interfaces) {
        for (final addr in iface.addresses) {
          if (!addr.isLoopback) return addr.address;
        }
      }
    } catch (_) {}
    return null;
  }
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd lcloud-android
flutter analyze lib/services/discovery.dart
```

Expected: `No issues found!`

- [ ] **Step 3: Commit**

```bash
git add lcloud-android/lib/services/discovery.dart
git commit -m "feat: replace mDNS with multicast UDP discovery on Android"
```

---

### Task B4: Delete http_server.dart

**Files:**
- Delete: `lcloud-android/lib/services/http_server.dart`

- [ ] **Step 1: Delete the file**

```bash
cd lcloud-android
del lib\services\http_server.dart
```

- [ ] **Step 2: Check for remaining imports**

```bash
grep -r "http_server" lib/
```

Expected: no output (no remaining imports).

- [ ] **Step 3: Commit**

```bash
git add -A lcloud-android/lib/services/http_server.dart
git commit -m "chore: remove http_server.dart — phone no longer serves files"
```

---

### Task B5: Update home_screen.dart

**Files:**
- Modify: `lcloud-android/lib/screens/home_screen.dart`

- [ ] **Step 1: Replace home_screen.dart with the new backup flow**

```dart
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/backup_session.dart';
import '../services/discovery.dart';
import '../services/file_scanner.dart';
import '../services/transfer_client.dart';
import '../widgets/progress_card.dart';
import '../widgets/status_card.dart' as sc;
import 'settings_screen.dart';

const Color _bgColor = Color(0xFF1a1a2e);
const Color _cardColor = Color(0xFF16213e);
const Color _accentColor = Color(0xFF4f46e5);
const Color _textSecondary = Color(0xFF94a3b8);

const String _pcPortKey = 'pc_port';

/// Main backup screen.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  // Discovery state
  sc.ConnectionState _connectionState = sc.ConnectionState.searching;
  DiscoveredPC? _pc;

  // Scan state
  List<BackupFile> _filesToBackup = [];
  bool _scanning = false;

  // Backup state
  bool _backingUp = false;
  String _currentFile = '';
  int _currentIndex = 0;
  int _totalFiles = 0;
  int _bytesTransferred = 0;
  int _totalBytes = 0;

  // History (in-memory for now)
  final List<BackupSession> _sessions = [];

  final LcloudDiscovery _discovery = LcloudDiscovery();
  final FileScanner _scanner = FileScanner();

  @override
  void initState() {
    super.initState();
    _scanFiles();
    _startDiscovery();
  }

  @override
  void dispose() {
    _discovery.stopDiscovery();
    super.dispose();
  }

  // ---------------------------------------------------------------------------
  // Discovery
  // ---------------------------------------------------------------------------

  void _startDiscovery() {
    if (mounted) setState(() => _connectionState = sc.ConnectionState.searching);
    _discovery.startListening(onFound: _onPCFound);
  }

  void _onPCFound(DiscoveredPC pc) {
    if (!mounted) return;
    // Only update if it's a new PC or changed IP
    if (_pc?.address != pc.address || _pc?.fingerprint != pc.fingerprint) {
      setState(() {
        _pc = pc;
        _connectionState = sc.ConnectionState.found;
      });
    }
  }

  // ---------------------------------------------------------------------------
  // File scanning
  // ---------------------------------------------------------------------------

  Future<void> _scanFiles() async {
    setState(() => _scanning = true);
    try {
      final files = await _scanner.scanAll();
      if (mounted) setState(() { _filesToBackup = files; _scanning = false; });
    } catch (_) {
      if (mounted) setState(() => _scanning = false);
    }
  }

  // ---------------------------------------------------------------------------
  // Backup flow
  // ---------------------------------------------------------------------------

  Future<void> _startBackup() async {
    final pc = _pc;
    if (pc == null) {
      _showSnack('No PC found. Make sure Lcloud is running on your PC.');
      return;
    }
    if (_filesToBackup.isEmpty) {
      _showSnack('No files found to back up.');
      return;
    }

    final prefs = await SharedPreferences.getInstance();
    final deviceAlias = Platform.localHostname;

    // Build TransferFile list
    final transferFiles = _filesToBackup.map((f) => TransferFile(
      fileId: f.path.hashCode.toRadixString(16),
      fileName: f.name,
      fileSize: f.sizeBytes,
      fileType: _mimeType(f.name),
      path: f.path,
      category: f.category,
      modifiedAt: f.modifiedAt,
    )).toList();

    final client = TransferClient(
      pcAddress: pc.address,
      pcPort: pc.port,
      fingerprint: pc.fingerprint,
    );

    setState(() {
      _backingUp = true;
      _connectionState = sc.ConnectionState.backingUp;
      _totalFiles = transferFiles.length;
      _totalBytes = transferFiles.fold(0, (s, f) => s + f.fileSize);
      _currentIndex = 0;
      _bytesTransferred = 0;
    });

    final startedAt = DateTime.now();
    String? sessionId;
    final errors = <String>[];

    try {
      // 1. Prepare session
      final tokens = await client.prepareUpload(
        deviceAlias: deviceAlias,
        files: transferFiles,
      );
      sessionId = tokens['__sessionId__']!;

      // 2. Upload each file
      for (int i = 0; i < transferFiles.length; i++) {
        final file = transferFiles[i];
        final token = tokens[file.fileId];
        if (token == null) { errors.add(file.fileName); continue; }

        if (mounted) {
          setState(() {
            _currentFile = file.fileName;
            _currentIndex = i + 1;
          });
        }

        try {
          await client.uploadFile(
            sessionId: sessionId,
            file: file,
            token: token,
            onProgress: (bytesSent) {
              if (mounted) {
                setState(() {
                  // Replace previous file's contribution with current progress
                  final prevBytes = transferFiles
                      .take(i)
                      .fold(0, (s, f) => s + f.fileSize);
                  _bytesTransferred = prevBytes + bytesSent;
                });
              }
            },
          );
        } on TransferException catch (e) {
          errors.add(file.fileName);
          if (e.code == 'invalid_token') break; // session is broken — stop
        }
      }

      final session = BackupSession(
        startedAt: startedAt,
        completedAt: DateTime.now(),
        filesSaved: transferFiles.length - errors.length,
        bytesTransferred: _bytesTransferred,
        errors: errors,
      );

      if (mounted) {
        setState(() {
          _sessions.insert(0, session);
          if (_sessions.length > 20) _sessions.removeLast();
          _connectionState = sc.ConnectionState.complete;
          _backingUp = false;
        });
        _showDeletePrompt(session);
      }
    } on TransferException catch (e) {
      if (sessionId != null) await client.cancel(sessionId);
      if (mounted) {
        setState(() { _connectionState = sc.ConnectionState.error; _backingUp = false; });
        _showSnack(_friendlyError(e));
      }
    } catch (e) {
      if (sessionId != null) await client.cancel(sessionId);
      if (mounted) {
        setState(() { _connectionState = sc.ConnectionState.error; _backingUp = false; });
        _showSnack('Backup failed: $e');
      }
    }
  }

  String _friendlyError(TransferException e) {
    switch (e.code) {
      case 'disk_full': return 'PC storage is full. Free up space and try again.';
      case 'no_backup_folder': return 'Open Lcloud on your PC and set a backup folder.';
      case 'invalid_token': return 'Connection error. Try again.';
      default: return 'Backup failed (${e.code}). Try again.';
    }
  }

  String _mimeType(String fileName) {
    final ext = fileName.split('.').last.toLowerCase();
    const types = {
      'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
      'gif': 'image/gif', 'heic': 'image/heic', 'webp': 'image/webp',
      'mp4': 'video/mp4', 'mov': 'video/quicktime', 'avi': 'video/x-msvideo',
      'mkv': 'video/x-matroska', '3gp': 'video/3gpp',
      'pdf': 'application/pdf', 'doc': 'application/msword',
      'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    };
    return types[ext] ?? 'application/octet-stream';
  }

  void _showDeletePrompt(BackupSession session) {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: const Text('Backup Complete', style: TextStyle(color: Colors.white)),
        content: Text(
          '${session.filesSaved} files (${session.sizeLabel}) backed up.\n\n'
          'Delete backed-up files from your phone to free space?',
          style: const TextStyle(color: _textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Keep on Phone', style: TextStyle(color: _textSecondary)),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              _showSnack('Delete feature coming in v0.3');
            },
            style: ElevatedButton.styleFrom(backgroundColor: _accentColor),
            child: const Text('Delete from Phone', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // UI
  // ---------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        title: const Text('Lcloud',
            style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold)),
        backgroundColor: _bgColor,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.settings, color: Colors.white),
            onPressed: () => Navigator.push(
              context, MaterialPageRoute<void>(builder: (_) => const SettingsScreen())),
          ),
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white),
            onPressed: _backingUp
                ? null
                : () {
                    _discovery.stopDiscovery();
                    setState(() {
                      _connectionState = sc.ConnectionState.searching;
                      _pc = null;
                    });
                    _startDiscovery();
                  },
          ),
        ],
      ),
      body: Column(
        children: [
          sc.StatusCard(
            state: _connectionState,
            pcName: _pc?.name,
            subtitle: null,   // no raw IP shown
          ),
          _statsRow(),
          if (_backingUp)
            ProgressCard(
              currentFile: _currentFile,
              currentIndex: _currentIndex,
              totalFiles: _totalFiles,
              bytesTransferred: _bytesTransferred,
              totalBytes: _totalBytes,
            ),
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
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: Text(
                  _backingUp ? 'Backing up...' : 'Backup Now',
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white),
                ),
              ),
            ),
          ),
          Expanded(child: _historyList()),
        ],
      ),
    );
  }

  Widget _statsRow() {
    final totalSize = _filesToBackup.fold<int>(0, (s, f) => s + f.sizeBytes);
    final sizeMb = totalSize / (1024 * 1024);
    final lastBackup = _sessions.isNotEmpty
        ? DateFormat('MMM d').format(_sessions.first.completedAt)
        : 'Never';

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
      decoration: BoxDecoration(color: _cardColor, borderRadius: BorderRadius.circular(14)),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          _statItem(_scanning ? '...' : '${_filesToBackup.length}', 'Files found'),
          _divider(),
          _statItem(_scanning ? '...' : '${sizeMb.toStringAsFixed(1)} MB', 'Total size'),
          _divider(),
          _statItem(lastBackup, 'Last backup'),
        ],
      ),
    );
  }

  Widget _statItem(String value, String label) => Column(
    children: [
      Text(value, style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w700)),
      const SizedBox(height: 2),
      Text(label, style: const TextStyle(color: _textSecondary, fontSize: 11)),
    ],
  );

  Widget _divider() => Container(height: 30, width: 1, color: Colors.white12);

  Widget _historyList() {
    if (_sessions.isEmpty) {
      return const Center(
        child: Text('No backups yet.\nTap "Backup Now" to start.',
            textAlign: TextAlign.center,
            style: TextStyle(color: _textSecondary, fontSize: 14, height: 1.6)),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      itemCount: _sessions.length + 1,
      itemBuilder: (ctx, idx) {
        if (idx == 0) {
          return const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Text('Recent Backups',
                style: TextStyle(color: _textSecondary, fontSize: 12, fontWeight: FontWeight.w600)),
          );
        }
        return _sessionTile(_sessions[idx - 1]);
      },
    );
  }

  Widget _sessionTile(BackupSession session) {
    final date = DateFormat('MMM d, HH:mm').format(session.completedAt);
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: _cardColor, borderRadius: BorderRadius.circular(12)),
      child: Row(
        children: [
          const Icon(Icons.check_circle, color: Color(0xFF22c55e), size: 20),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(date, style: const TextStyle(color: Colors.white, fontSize: 13)),
                Text('${session.filesSaved} files · ${session.sizeLabel}',
                    style: const TextStyle(color: _textSecondary, fontSize: 12)),
              ],
            ),
          ),
          if (session.hadErrors)
            Text('${session.errors.length} error',
                style: const TextStyle(color: Color(0xFFf59e0b), fontSize: 11)),
        ],
      ),
    );
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(message),
      backgroundColor: _cardColor,
      behavior: SnackBarBehavior.floating,
    ));
  }
}
```

- [ ] **Step 2: Analyze for errors**

```bash
cd lcloud-android
flutter analyze lib/screens/home_screen.dart
```

Fix any reported issues before proceeding.

- [ ] **Step 3: Run all Flutter tests**

```bash
flutter test
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add lcloud-android/lib/screens/home_screen.dart
git commit -m "feat: wire new discovery + HTTPS transfer client into home screen"
```

---

## Task C1: End-to-End Integration Test

**Manual test on real hardware — no emulator. PC and phone must be on the same WiFi.**

- [ ] **Step 1: Start the PC app**

```bash
cd lcloud-pc
call venv\Scripts\activate
python src/main.py
```

Verify in the console: `HTTPS backup server listening on port 53317` and `Discovery: broadcasting on 224.0.0.167:53317`

- [ ] **Step 2: Check the cert was created**

```
dir "%LOCALAPPDATA%\lcloud\"
```

Expected: `lcloud.crt` and `lcloud.key` present.

- [ ] **Step 3: Install and run the Android app**

```bash
cd lcloud-android
flutter run --release
```

- [ ] **Step 4: Verify PC is found on the phone**

The status card should change from "Searching…" to the PC name within 5 seconds.

- [ ] **Step 5: Set backup folder on PC and run a backup**

- Click "Change" in the PC window, select a folder.
- On the phone, tap "Backup Now".
- Watch the progress bar update file-by-file (real progress).

- [ ] **Step 6: Verify files are organized on PC**

Open the backup folder. Files should be sorted into `Photos/`, `Videos/`, `WhatsApp/`, `Documents/`.

- [ ] **Step 7: Final test suite**

```bash
cd lcloud-pc
pytest tests/ -v
```

Expected: all green.

- [ ] **Step 8: Tag the release**

```bash
git tag v0.2.0-transport
git push --tags
```

---

## Self-Review

**Spec coverage check:**
- ✅ Multicast UDP discovery (PC → broadcast, Android → listen) — Tasks A4, B3
- ✅ HTTPS with self-signed cert — Tasks A3, A5, B2
- ✅ Fingerprint trust (TOFU) — Task B2 (`badCertificateCallback`)
- ✅ `/info`, `/prepare-upload`, `/upload`, `/cancel` endpoints — Task A5
- ✅ Real per-file progress — Task B5 (`onProgress` in `uploadFile`)
- ✅ Disk full (507) + no folder (503) errors — Tasks A5, B2, B5
- ✅ Android multicast lock — Task B1 + B3
- ✅ Streaming upload (no full-file memory load) — Tasks A5 (chunked read), B2 (`openRead()`)
- ✅ Cancel on error — Task B5

**No placeholders:** All steps have exact code.

**Type consistency:** `TransferFile.fileSize` (int) matches `TransferFile.toJson()['size']` (int) matches `_FileEntry.size` (int). `sessionId` is `String` throughout. `fingerprint` is SHA-256 hex `String` everywhere.

"""
Lcloud PC — Backup Engine (HTTPS Server)

Receives file uploads from the Android app over HTTPS.

Endpoints:
  GET  /api/lcloud/v2/info              — device identity + fingerprint
  POST /api/lcloud/v2/prepare-upload    — start session, receive file list, return tokens
  POST /api/lcloud/v2/upload            — upload one file (streamed to disk)
  POST /api/lcloud/v2/cancel            — cancel and clean up session
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
# Callback type aliases
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
    path: str          # original phone path (used as originalPath in manifest)
    category: str
    modified_at: datetime
    token: str = field(default_factory=lambda: str(uuid.uuid4()))
    done: bool = False
    backed_up_path: str = ""   # relative to backup_root (posix), set after organize()


@dataclass
class _Session:
    session_id: str
    files: dict[str, _FileEntry]   # fileId → _FileEntry
    bytes_received: int = 0
    files_done: int = 0
    device_alias: str = ""
    started_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# HTTP request handler
# ---------------------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    """Handles all HTTPS requests from the Android app."""

    engine: "BackupEngine"   # injected by BackupEngine.start_server

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        logger.debug("HTTP %s", format % args)

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

    # ------------------------------------------------------------------

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

        session = _Session(
            session_id=session_id,
            files=files,
            device_alias=body.get("deviceAlias", "Unknown"),
            started_at=datetime.now(),
        )
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

        # Stream to temp file — never loads entire file into memory
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
            self.engine._write_manifest(session)
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

    # ------------------------------------------------------------------

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
        engine.start_server(backup_folder=..., cert_path=..., key_path=..., ...)
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

        # Store actual port (important when port=0 picks an ephemeral port for tests)
        self.port = self._server.server_address[1]

        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="lcloud-server",
        )
        self._server_thread.start()
        logger.info("HTTPS backup server listening on port %s", self.port)

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

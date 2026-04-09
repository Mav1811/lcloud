"""
Lcloud PC App — Backup Engine
HTTP server that receives backup requests from the Android phone and
downloads files from the phone's HTTP server.
"""
import json
import logging
import threading
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable

import requests

from config import ANDROID_SERVER_PORT, PC_PORT
from core.file_organizer import FileOrganizer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Callback type aliases
# ---------------------------------------------------------------------------
ProgressCallback = Callable[[str, int, int, int, int], None]
# (filename, current_file_index, total_files, bytes_done, bytes_total)

CompleteCallback = Callable[[int, int, list[str]], None]
# (files_saved, bytes_saved, errors)


# ---------------------------------------------------------------------------
# HTTP request handler
# ---------------------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    """Handles HTTP requests from the Android app."""

    # Injected by _BackupServer
    engine: "BackupEngine"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        logger.debug("HTTP %s", format % args)

    def do_GET(self) -> None:
        if self.path == "/ping":
            self._json_response(200, {"status": "ok", "app": "lcloud-pc", "version": "0.1.0"})
        else:
            self._json_response(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path == "/announce":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._json_response(400, {"error": "invalid json"})
                return

            phone_ip = self.client_address[0]
            phone_port = data.get("server_port", ANDROID_SERVER_PORT)
            files = data.get("files", [])

            logger.info(
                "Backup announced from %s — %d files", phone_ip, len(files)
            )

            if not self.engine.backup_folder:
                self._json_response(503, {"error": "no backup folder configured"})
                return

            self._json_response(200, {"ready": True, "session_id": "session-1"})

            # Start download in a background thread so we don't block this request
            threading.Thread(
                target=self.engine._download_files,
                args=(phone_ip, phone_port, files),
                daemon=True,
            ).start()

        else:
            self._json_response(404, {"error": "not found"})

    # ------------------------------------------------------------------

    def _json_response(self, code: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# Backup Engine
# ---------------------------------------------------------------------------

class BackupEngine:
    """
    Manages the PC-side HTTP server and file download logic.

    Usage:
        engine = BackupEngine()
        engine.start_server(
            backup_folder=Path("D:/Backup"),
            on_progress=my_progress_cb,
            on_complete=my_complete_cb,
        )
        # ... app runs ...
        engine.stop_server()
    """

    def __init__(self) -> None:
        self.backup_folder: Path | None = None
        self._on_progress: ProgressCallback | None = None
        self._on_complete: CompleteCallback | None = None
        self._server: HTTPServer | None = None
        self._server_thread: threading.Thread | None = None
        self._organizer = FileOrganizer()

    def start_server(
        self,
        backup_folder: Path,
        on_progress: ProgressCallback | None = None,
        on_complete: CompleteCallback | None = None,
        port: int = PC_PORT,
    ) -> None:
        """Start the HTTP server that listens for phone backup announcements."""
        if self._server:
            logger.warning("Server already running — call stop_server() first.")
            return

        self.backup_folder = backup_folder
        self._on_progress = on_progress
        self._on_complete = on_complete

        # Inject `self` into the handler class (thread-safe: one server instance)
        _Handler.engine = self

        self._server = HTTPServer(("0.0.0.0", port), _Handler)
        self._server_thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._server_thread.start()
        logger.info("Backup server listening on port %s", port)

    def stop_server(self) -> None:
        """Shut down the HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server = None
            self._server_thread = None
            logger.info("Backup server stopped.")

    def set_backup_folder(self, folder: Path) -> None:
        """Update the backup destination folder at runtime."""
        self.backup_folder = folder
        logger.info("Backup folder set to: %s", folder)

    # ------------------------------------------------------------------
    # Internal: download loop
    # ------------------------------------------------------------------

    def _download_files(
        self,
        phone_ip: str,
        phone_port: int,
        files: list[dict],
    ) -> None:
        """Download all files from the phone's HTTP server."""
        base_url = f"http://{phone_ip}:{phone_port}"
        total_files = len(files)
        total_bytes = sum(f.get("size", 0) for f in files)
        bytes_done = 0
        files_saved = 0
        errors: list[str] = []

        logger.info(
            "Starting download: %d files, %d bytes from %s",
            total_files, total_bytes, base_url,
        )

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            for idx, file_meta in enumerate(files):
                name = file_meta.get("name", f"file_{idx}")
                path_on_phone = file_meta.get("path", "")
                size = file_meta.get("size", 0)
                modified_ts = file_meta.get("modified_at")
                modified_at = (
                    datetime.fromisoformat(modified_ts) if modified_ts else datetime.now()
                )

                # Check if path contains WhatsApp marker for organizer
                organizer_name = path_on_phone if path_on_phone else name

                if self._on_progress:
                    self._on_progress(name, idx + 1, total_files, bytes_done, total_bytes)

                try:
                    encoded_path = urllib.parse.quote(path_on_phone, safe="")
                    url = f"{base_url}/file/{encoded_path}"
                    tmp_path = Path(tmpdir) / f"tmp_{idx}_{name}"

                    with requests.get(url, stream=True, timeout=30) as resp:
                        resp.raise_for_status()
                        with open(tmp_path, "wb") as fout:
                            for chunk in resp.iter_content(chunk_size=65536):
                                fout.write(chunk)
                                bytes_done += len(chunk)

                    if self.backup_folder:
                        self._organizer.organize(
                            source_path=tmp_path,
                            original_name=name,
                            backup_root=self.backup_folder,
                            modified_at=modified_at,
                        )
                        files_saved += 1

                except requests.RequestException as exc:
                    msg = f"Failed to download {name}: {exc}"
                    logger.error(msg)
                    errors.append(msg)

        logger.info(
            "Backup complete: %d/%d files saved, %d errors",
            files_saved, total_files, len(errors),
        )

        if self._on_complete:
            self._on_complete(files_saved, bytes_done, errors)

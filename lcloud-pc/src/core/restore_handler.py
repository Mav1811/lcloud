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
        # token → absolute path of the backed-up file
        self._tokens: dict[str, str] = {}

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

"""
Lcloud PC App — Configuration
All constants and settings live here. Never use magic strings elsewhere.
"""
import json
import logging
import os
from pathlib import Path

APP_NAME = "Lcloud"
APP_VERSION = "0.2.0"

# Networking — LocalSend-inspired protocol
LCLOUD_PORT = 53317          # PC HTTPS server (same port as LocalSend)
MULTICAST_GROUP = "224.0.0.167"
MULTICAST_PORT = 53317
PROTOCOL_VERSION = "1.0"

# Disk space: refuse backup if free space on backup drive drops below this
MIN_FREE_SPACE_BYTES = 200 * 1024 * 1024  # 200 MB buffer

# File categories (extensions → folder name)
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".heic", ".webp", ".bmp", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".3gp", ".wmv", ".m4v", ".flv"}
DOCUMENT_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".csv", ".odt", ".ods", ".odp", ".rtf",
}
WHATSAPP_PATH_MARKERS = ["whatsapp", "WhatsApp"]

CATEGORY_FOLDERS = {
    "whatsapp": "WhatsApp",
    "photo": "Photos",
    "video": "Videos",
    "document": "Documents",
    "other": "Other",
}

# Restore manifests — written after every completed backup session
MANIFEST_SUBDIR = ".lcloud/manifests"   # relative to backup_root

WHATSAPP_SUBCATEGORIES = {
    "image": "Images",
    "video": "Video",
    "audio": "Audio",
    "document": "Documents",
    "gif": "GIF",
}

# Settings storage
def _settings_path() -> Path:
    appdata = os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    return Path(appdata) / "lcloud" / "settings.json"

# Log file
def _log_path() -> Path:
    appdata = os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    return Path(appdata) / "lcloud" / "lcloud.log"

# TLS certificate paths
def _cert_path() -> Path:
    appdata = os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    return Path(appdata) / "lcloud" / "lcloud.crt"

def _key_path() -> Path:
    appdata = os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    return Path(appdata) / "lcloud" / "lcloud.key"

CERT_PATH: Path = _cert_path()
KEY_PATH: Path = _key_path()


class Settings:
    """Persistent settings — loaded from and saved to JSON."""

    def __init__(self) -> None:
        self.backup_folder: str | None = None
        self.dark_mode: bool = True
        self.port: int = LCLOUD_PORT
        self._path = _settings_path()

    def load(self) -> None:
        """Load settings from disk. Silently creates defaults if file missing."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self.backup_folder = data.get("backup_folder")
                self.dark_mode = data.get("dark_mode", True)
                self.port = data.get("port", LCLOUD_PORT)
        except (json.JSONDecodeError, OSError) as exc:
            logging.warning("Could not load settings: %s — using defaults.", exc)

    def save(self) -> None:
        """Save current settings to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "backup_folder": self.backup_folder,
                "dark_mode": self.dark_mode,
                "port": self.port,
            }
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as exc:
            logging.error("Could not save settings: %s", exc)


def setup_logging() -> None:
    """Configure logging to file + console."""
    log_path = _log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

"""
Lcloud PC App — File Organizer
Sorts incoming backup files into the correct folder structure.
"""
import logging
import shutil
from datetime import datetime
from pathlib import Path

from config import (
    CATEGORY_FOLDERS,
    DOCUMENT_EXTENSIONS,
    PHOTO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    WHATSAPP_PATH_MARKERS,
    WHATSAPP_SUBCATEGORIES,
)

logger = logging.getLogger(__name__)


class FileOrganizer:
    """
    Moves a file to the correct destination under the backup root folder.

    Folder structure:
        {backup_root}/
            Photos/YYYY/MM/
            Videos/YYYY/MM/
            WhatsApp/Images|Video|Audio|Documents|GIF/
            Documents/YYYY/MM/
            Other/YYYY/MM/
    """

    def organize(
        self,
        source_path: Path,
        original_name: str,
        backup_root: Path,
        modified_at: datetime | None = None,
    ) -> Path:
        """
        Copy *source_path* into the right sub-folder of *backup_root*.

        Args:
            source_path:   Temporary path where the downloaded file lives.
            original_name: Original filename from the phone (used for extension + dating).
            backup_root:   Root backup folder chosen by the user.
            modified_at:   File's last-modified timestamp (falls back to now).

        Returns:
            The final destination path where the file was saved.
        """
        modified_at = modified_at or datetime.now()
        category = self._detect_category(original_name)
        dest_dir = self._destination_dir(
            backup_root, category, original_name, modified_at
        )
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = self._safe_dest_path(dest_dir, original_name)
        shutil.copy2(source_path, dest_path)
        logger.info("Organized %s → %s", original_name, dest_path)
        return dest_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_category(self, filename: str) -> str:
        """Return one of: 'whatsapp', 'photo', 'video', 'document', 'other'."""
        lower = filename.lower()
        # WhatsApp is detected by path markers embedded in the filename or
        # by callers passing the full path as `filename` — we check both.
        for marker in WHATSAPP_PATH_MARKERS:
            if marker.lower() in lower:
                return "whatsapp"

        ext = Path(filename).suffix.lower()
        if ext in PHOTO_EXTENSIONS:
            return "photo"
        if ext in VIDEO_EXTENSIONS:
            return "video"
        if ext in DOCUMENT_EXTENSIONS:
            return "document"
        return "other"

    def _destination_dir(
        self,
        backup_root: Path,
        category: str,
        filename: str,
        modified_at: datetime,
    ) -> Path:
        folder_name = CATEGORY_FOLDERS[category]
        year = modified_at.strftime("%Y")
        month = modified_at.strftime("%m")

        if category == "whatsapp":
            subcategory = self._whatsapp_subcategory(filename)
            return backup_root / folder_name / subcategory

        return backup_root / folder_name / year / month

    def _whatsapp_subcategory(self, filename: str) -> str:
        """Return the WhatsApp sub-folder name based on file type."""
        ext = Path(filename).suffix.lower()
        if ext in PHOTO_EXTENSIONS:
            return WHATSAPP_SUBCATEGORIES["image"]
        if ext in VIDEO_EXTENSIONS:
            return WHATSAPP_SUBCATEGORIES["video"]
        if ext in {".mp3", ".ogg", ".opus", ".m4a", ".aac", ".wav"}:
            return WHATSAPP_SUBCATEGORIES["audio"]
        if ext == ".gif":
            return WHATSAPP_SUBCATEGORIES["gif"]
        return WHATSAPP_SUBCATEGORIES["document"]

    def _safe_dest_path(self, dest_dir: Path, filename: str) -> Path:
        """
        Return a path that does not already exist.
        If `filename` exists, append _HHMMSS before the extension.
        """
        basename = Path(filename).name   # strip any leading path from phone
        stem = Path(basename).stem
        suffix = Path(basename).suffix
        candidate = dest_dir / basename

        if not candidate.exists():
            return candidate

        # Collision — append timestamp
        timestamp = datetime.now().strftime("%H%M%S")
        candidate = dest_dir / f"{stem}_{timestamp}{suffix}"

        # Extreme edge case: still collides (same second, same file)
        counter = 1
        while candidate.exists():
            candidate = dest_dir / f"{stem}_{timestamp}_{counter}{suffix}"
            counter += 1

        return candidate

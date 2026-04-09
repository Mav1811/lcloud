"""
Tests for FileOrganizer — path logic, category detection, collision handling.
Run with: pytest tests/ -v
"""
import sys
from pathlib import Path
from datetime import datetime
import shutil
import tempfile

# Ensure src/ is on the path when running tests from project root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.file_organizer import FileOrganizer


# ---------------------------------------------------------------------------
# Category detection
# ---------------------------------------------------------------------------

class TestCategoryDetection:
    def setup_method(self):
        self.organizer = FileOrganizer()

    def test_photo_extensions(self):
        for ext in [".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif", ".bmp"]:
            assert self.organizer._detect_category(f"photo{ext}") == "photo"

    def test_video_extensions(self):
        for ext in [".mp4", ".mov", ".avi", ".mkv", ".3gp"]:
            assert self.organizer._detect_category(f"video{ext}") == "video"

    def test_document_extensions(self):
        for ext in [".pdf", ".doc", ".docx", ".xls", ".txt", ".csv"]:
            assert self.organizer._detect_category(f"report{ext}") == "document"

    def test_whatsapp_marker_in_name(self):
        assert self.organizer._detect_category("WhatsApp Image 2025-01-01.jpg") == "whatsapp"

    def test_whatsapp_marker_lowercase(self):
        assert self.organizer._detect_category("/storage/whatsapp/media/photo.jpg") == "whatsapp"

    def test_unknown_extension_is_other(self):
        assert self.organizer._detect_category("archive.zip") == "other"
        assert self.organizer._detect_category("data.bin") == "other"


# ---------------------------------------------------------------------------
# Destination directory logic
# ---------------------------------------------------------------------------

class TestDestinationDir:
    def setup_method(self):
        self.organizer = FileOrganizer()
        self.root = Path("/fake/backup")
        self.dt = datetime(2025, 4, 9, 10, 30, 0)

    def test_photo_path(self):
        dest = self.organizer._destination_dir(self.root, "photo", "img.jpg", self.dt)
        assert dest == self.root / "Photos" / "2025" / "04"

    def test_video_path(self):
        dest = self.organizer._destination_dir(self.root, "video", "vid.mp4", self.dt)
        assert dest == self.root / "Videos" / "2025" / "04"

    def test_document_path(self):
        dest = self.organizer._destination_dir(self.root, "document", "doc.pdf", self.dt)
        assert dest == self.root / "Documents" / "2025" / "04"

    def test_other_path(self):
        dest = self.organizer._destination_dir(self.root, "other", "file.zip", self.dt)
        assert dest == self.root / "Other" / "2025" / "04"

    def test_whatsapp_image_path(self):
        dest = self.organizer._destination_dir(self.root, "whatsapp", "wa_img.jpg", self.dt)
        assert dest == self.root / "WhatsApp" / "Images"

    def test_whatsapp_video_path(self):
        dest = self.organizer._destination_dir(self.root, "whatsapp", "wa_vid.mp4", self.dt)
        assert dest == self.root / "WhatsApp" / "Video"

    def test_whatsapp_audio_path(self):
        dest = self.organizer._destination_dir(self.root, "whatsapp", "wa_audio.opus", self.dt)
        assert dest == self.root / "WhatsApp" / "Audio"

    def test_whatsapp_document_path(self):
        dest = self.organizer._destination_dir(self.root, "whatsapp", "wa_doc.pdf", self.dt)
        assert dest == self.root / "WhatsApp" / "Documents"


# ---------------------------------------------------------------------------
# Collision handling
# ---------------------------------------------------------------------------

class TestCollisionHandling:
    def setup_method(self):
        self.organizer = FileOrganizer()
        self.tmpdir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.tmpdir)

    def test_no_collision_returns_original_name(self):
        dest = self.organizer._safe_dest_path(self.tmpdir, "photo.jpg")
        assert dest == self.tmpdir / "photo.jpg"

    def test_collision_appends_timestamp(self):
        # Create the file so there's a collision
        (self.tmpdir / "photo.jpg").write_bytes(b"existing")
        dest = self.organizer._safe_dest_path(self.tmpdir, "photo.jpg")
        assert dest != self.tmpdir / "photo.jpg"
        assert dest.stem.startswith("photo_")
        assert dest.suffix == ".jpg"
        assert not dest.exists()  # The safe path must not yet exist


# ---------------------------------------------------------------------------
# End-to-end organize (with real temp files)
# ---------------------------------------------------------------------------

class TestOrganizeEndToEnd:
    def setup_method(self):
        self.organizer = FileOrganizer()
        self.tmpdir = Path(tempfile.mkdtemp())
        self.backup_root = self.tmpdir / "backup"

    def teardown_method(self):
        shutil.rmtree(self.tmpdir)

    def test_organizes_photo_into_correct_folder(self):
        src = self.tmpdir / "test.jpg"
        src.write_bytes(b"fake jpeg data")
        dt = datetime(2025, 3, 15)

        result = self.organizer.organize(src, "test.jpg", self.backup_root, dt)

        assert result.exists()
        assert "Photos" in str(result)
        assert "2025" in str(result)
        assert "03" in str(result)

    def test_organizes_video(self):
        src = self.tmpdir / "clip.mp4"
        src.write_bytes(b"fake video")
        result = self.organizer.organize(src, "clip.mp4", self.backup_root)
        assert "Videos" in str(result)

    def test_organizes_whatsapp_image(self):
        src = self.tmpdir / "wa_img.jpg"
        src.write_bytes(b"fake whatsapp img")
        result = self.organizer.organize(
            src, "WhatsApp Image 2025-01-01.jpg", self.backup_root
        )
        assert "WhatsApp" in str(result)
        assert "Images" in str(result)

    def test_does_not_overwrite_existing(self):
        src1 = self.tmpdir / "photo1.jpg"
        src2 = self.tmpdir / "photo2.jpg"
        src1.write_bytes(b"original")
        src2.write_bytes(b"duplicate")
        dt = datetime(2025, 4, 1)

        r1 = self.organizer.organize(src1, "photo.jpg", self.backup_root, dt)
        r2 = self.organizer.organize(src2, "photo.jpg", self.backup_root, dt)

        assert r1 != r2
        assert r1.exists()
        assert r2.exists()

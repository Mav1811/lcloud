"""
Tests for BackupEngine — server start/stop, error handling.
Uses mocking to avoid real HTTP connections.
Run with: pytest tests/ -v
"""
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.backup_engine import BackupEngine


class TestBackupEngineLifecycle:
    def test_start_stop_server(self):
        """Server starts and stops without error."""
        engine = BackupEngine()
        engine.start_server(backup_folder=Path("."), port=52099)
        time.sleep(0.1)  # Let server thread start
        engine.stop_server()

    def test_double_start_is_safe(self):
        """Calling start_server twice does not raise."""
        engine = BackupEngine()
        engine.start_server(backup_folder=Path("."), port=52098)
        time.sleep(0.05)
        engine.start_server(backup_folder=Path("."), port=52098)  # Second call — no crash
        engine.stop_server()

    def test_stop_without_start_is_safe(self):
        """Calling stop before start does not raise."""
        engine = BackupEngine()
        engine.stop_server()  # Should not raise

    def test_set_backup_folder_updates_attribute(self):
        engine = BackupEngine()
        folder = Path("/tmp/test_backup")
        engine.set_backup_folder(folder)
        assert engine.backup_folder == folder


class TestDownloadFiles:
    """Test the download logic with mocked HTTP."""

    def setup_method(self):
        import tempfile
        self.tmpdir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_empty_file_list_calls_complete(self):
        engine = BackupEngine()
        engine.backup_folder = self.tmpdir

        complete_calls = []
        engine._on_complete = lambda fs, bs, errs: complete_calls.append((fs, bs, errs))

        engine._download_files("127.0.0.1", 52001, [])
        assert len(complete_calls) == 1
        files_saved, bytes_saved, errors = complete_calls[0]
        assert files_saved == 0
        assert errors == []

    @patch("core.backup_engine.requests.get")
    def test_failed_download_goes_to_errors(self, mock_get):
        """When requests raises, the file is counted as an error, not a crash."""
        import requests as req
        mock_get.side_effect = req.RequestException("connection refused")

        engine = BackupEngine()
        engine.backup_folder = self.tmpdir

        complete_calls = []
        engine._on_complete = lambda fs, bs, errs: complete_calls.append((fs, bs, errs))

        files = [{"name": "photo.jpg", "path": "/sdcard/photo.jpg", "size": 100}]
        engine._download_files("127.0.0.1", 52001, files)

        assert len(complete_calls) == 1
        _, _, errors = complete_calls[0]
        assert len(errors) == 1
        assert "photo.jpg" in errors[0]

    @patch("core.backup_engine.requests.get")
    def test_successful_download_calls_organizer(self, mock_get):
        """When download succeeds, FileOrganizer.organize is called."""
        # Create a mock response that yields bytes
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_content = MagicMock(return_value=[b"fake file data"])
        mock_get.return_value = mock_resp

        engine = BackupEngine()
        engine.backup_folder = self.tmpdir

        with patch.object(engine._organizer, "organize") as mock_organize:
            mock_organize.return_value = self.tmpdir / "organized_photo.jpg"
            complete_calls = []
            engine._on_complete = lambda fs, bs, errs: complete_calls.append((fs, bs, errs))

            files = [{"name": "photo.jpg", "path": "/sdcard/photo.jpg", "size": 14}]
            engine._download_files("127.0.0.1", 52001, files)

            assert mock_organize.called
            assert complete_calls[0][0] == 1  # 1 file saved
            assert complete_calls[0][2] == []  # no errors

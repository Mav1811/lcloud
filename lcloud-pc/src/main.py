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
    """
    Owns every component and wires them together.
    Using a class ensures all callbacks exist before any component
    stores a reference to them.
    """

    def __init__(self) -> None:
        setup_logging()
        logger.info("Lcloud starting up...")

        self.settings = Settings()
        self.settings.load()

        # Load or generate TLS certificate (runs once on first launch)
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
        self.tray = LcloudTray(
            on_open=self.window.show,
            on_quit=self._quit,
        )
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
        logger.info("Backup folder set to: %s", folder)

    def _on_backup_now(self) -> None:
        self.window.show_info(
            "Start Backup on Phone",
            "Open the Lcloud app on your Android phone and tap  Backup Now  to start.",
        )

    def _on_settings_change(self, port: int) -> None:
        self.settings.port = port
        self.settings.save()
        logger.info("Settings saved — port: %s (restart to apply)", port)

    def _on_disk_full(self, free_bytes: int, needed_bytes: int) -> None:
        free_mb   = free_bytes   // (1024 * 1024)
        needed_mb = needed_bytes // (1024 * 1024)
        self.window.show_warning(
            "Not Enough Disk Space",
            f"Backup stopped \u2014 not enough space on PC.\n\n"
            f"Free space:   {free_mb} MB\n"
            f"Space needed: {needed_mb} MB\n\n"
            f"Free up space on your PC and try again.",
        )
        self.window.update_status("Backup stopped \u2014 not enough disk space", "#ef4444")

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

        # Restore saved backup folder in UI
        if self.settings.backup_folder:
            folder = Path(self.settings.backup_folder)
            if folder.exists():
                self.window.set_backup_folder(folder)
                self.engine.set_backup_folder(folder)

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

        logger.info(
            "All services started. Fingerprint: %s...", self._fingerprint[:16]
        )
        self.window.mainloop()
        logger.info("Lcloud exited.")
        sys.exit(0)


def main() -> None:
    app = LcloudApp()
    app.run()


if __name__ == "__main__":
    main()

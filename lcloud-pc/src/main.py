"""
Lcloud PC App — Entry Point
All components are wired together through LcloudApp so callbacks
are always defined before they are referenced.
"""
import logging
import sys
from pathlib import Path

from config import Settings, setup_logging
from core.backup_engine import BackupEngine
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

        self._connected_phone: dict | None = None  # {name, address, port}

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
            on_phone_found=self._on_phone_found,
            on_phone_lost=self._on_phone_lost,
            port=self.settings.port,
        )

    # ------------------------------------------------------------------
    # Callbacks — all defined before any component runs
    # ------------------------------------------------------------------

    def _on_folder_change(self, folder: Path) -> None:
        self.settings.backup_folder = str(folder)
        self.settings.save()
        self.engine.set_backup_folder(folder)
        logger.info("Backup folder set to: %s", folder)

    def _on_backup_now(self) -> None:
        if self._connected_phone:
            name = self._connected_phone["name"]
            self.window.show_info(
                "Start Backup on Phone",
                f"'{name}' is connected.\n\n"
                f"Tap  Backup Now  in the Lcloud app on your Android phone to start the backup.",
            )
        else:
            self.window.show_info(
                "No Phone Connected",
                "No phone found on WiFi.\n\n"
                "Make sure:\n"
                "  \u2022 Both devices are on the same WiFi network\n"
                "  \u2022 The Lcloud app is open on your Android phone",
            )

    def _on_settings_change(self, port: int) -> None:
        self.settings.port = port
        self.settings.save()
        logger.info("Settings saved — port: %s (restart to apply)", port)

    def _on_phone_found(self, name: str, address: str, port: int) -> None:
        display = name.split(".")[0]
        self._connected_phone = {"name": display, "address": address, "port": port}
        self.engine.set_phone(address, port)
        self.window.update_phone_status(connected=True, phone_name=display)
        self.tray.set_tooltip(f"Lcloud \u2014 {display} connected")
        logger.info("Phone connected: %s @ %s:%s", display, address, port)

    def _on_phone_lost(self, name: str) -> None:
        self._connected_phone = None
        self.engine.set_phone(None, None)
        self.window.update_phone_status(connected=False)
        self.tray.set_tooltip("Lcloud \u2014 Waiting for phone")
        logger.info("Phone disconnected: %s", name)

    def _on_disk_full(self, free_bytes: int, needed_bytes: int) -> None:
        free_mb = free_bytes // (1024 * 1024)
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
        # Schedule destroy on the main thread (tray calls this from a daemon thread)
        self.window.after(0, self.window.destroy)

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def run(self) -> None:
        # Restore saved backup folder
        if self.settings.backup_folder:
            folder = Path(self.settings.backup_folder)
            if folder.exists():
                self.window.set_backup_folder(folder)
                self.engine.set_backup_folder(folder)

        backup_folder = (
            Path(self.settings.backup_folder)
            if self.settings.backup_folder
            else Path.home() / "lcloud_backup"
        )

        self.engine.start_server(
            backup_folder=backup_folder,
            on_progress=self.window.update_progress,
            on_complete=self.window.complete_progress,
            on_disk_full=self._on_disk_full,
            port=self.settings.port,
        )
        self.discovery.start()
        self.tray.start()

        logger.info("All services started. Running UI loop.")
        self.window.mainloop()
        # mainloop() returns when window is destroyed (on quit)
        logger.info("Lcloud exited.")
        sys.exit(0)


def main() -> None:
    app = LcloudApp()
    app.run()


if __name__ == "__main__":
    main()

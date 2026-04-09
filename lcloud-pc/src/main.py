"""
Lcloud PC App — Entry Point
Wires together: settings, discovery, backup engine, tray, and main window.
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


def main() -> None:
    setup_logging()
    logger.info("Lcloud starting up...")

    settings = Settings()
    settings.load()

    # --- Create components ---
    window = LcloudWindow(
        on_folder_change=_on_folder_change,
        on_backup_now=_on_backup_now,
    )

    engine = BackupEngine()
    tray = LcloudTray(
        on_open=window.show,
        on_quit=_quit,
    )

    discovery = LcloudDiscovery(
        on_phone_found=_on_phone_found,
        on_phone_lost=_on_phone_lost,
        port=settings.port,
    )

    # --- Inject dependencies into callbacks via closures ---
    def _on_folder_change(folder: Path) -> None:
        settings.backup_folder = str(folder)
        settings.save()
        engine.set_backup_folder(folder)
        logger.info("Backup folder changed to: %s", folder)

    def _on_backup_now() -> None:
        # In v0.1 this signals the engine to request backup from connected phone
        # Full implementation requires phone connection state tracking (v0.2)
        logger.info("Backup Now requested by user.")
        window.update_status("Waiting for phone to respond...", "#f59e0b")

    def _on_phone_found(name: str, address: str, port: int) -> None:
        logger.info("Phone found: %s @ %s:%s", name, address, port)
        window.update_phone_status(connected=True, phone_name=name.split(".")[0])
        tray.set_tooltip(f"Lcloud — Phone connected: {name}")

    def _on_phone_lost(name: str) -> None:
        logger.info("Phone lost: %s", name)
        window.update_phone_status(connected=False)
        tray.set_tooltip("Lcloud — No phone connected")

    def _quit() -> None:
        logger.info("Quit requested.")
        discovery.stop()
        engine.stop_server()
        window.quit()
        sys.exit(0)

    # --- Restore previous backup folder ---
    if settings.backup_folder:
        folder = Path(settings.backup_folder)
        if folder.exists():
            window.set_backup_folder(folder)
            engine.set_backup_folder(folder)

    # --- Start services ---
    engine.start_server(
        backup_folder=Path(settings.backup_folder) if settings.backup_folder else Path.home() / "lcloud_backup",
        on_progress=window.update_progress,
        on_complete=window.complete_progress,
        port=settings.port,
    )
    discovery.start()
    tray.start()

    logger.info("All services started. Running UI loop.")
    window.mainloop()


if __name__ == "__main__":
    main()

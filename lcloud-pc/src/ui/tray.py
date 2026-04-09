"""
Lcloud PC App — System Tray Icon
Keeps the app running in the background after the main window is closed.
"""
import logging
import threading
from typing import Callable

from PIL import Image, ImageDraw, ImageFont
import pystray
from pystray import MenuItem as Item

logger = logging.getLogger(__name__)


def _create_icon_image() -> Image.Image:
    """
    Create a simple 64x64 icon with an indigo background and white 'L'.
    This is a placeholder until a proper icon asset is added.
    """
    size = 64
    img = Image.new("RGBA", (size, size), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded rectangle (indigo)
    draw.rounded_rectangle([(0, 0), (size - 1, size - 1)], radius=14, fill="#4f46e5")

    # Letter 'L' centered
    try:
        font = ImageFont.truetype("arialbd.ttf", 38)
    except (IOError, OSError):
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), "L", font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2 - bbox[0]
    y = (size - text_h) // 2 - bbox[1]
    draw.text((x, y), "L", fill="white", font=font)

    return img


class LcloudTray:
    """
    Manages the system tray icon.

    The tray runs in a background thread.
    Closing the main window hides it — the tray is the only way to quit.
    """

    def __init__(
        self,
        on_open: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
    ) -> None:
        self._on_open = on_open or (lambda: None)
        self._on_quit = on_quit or (lambda: None)
        self._icon: pystray.Icon | None = None

    def start(self) -> None:
        """Start the tray icon in a daemon thread."""
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        logger.info("System tray icon started.")

    def stop(self) -> None:
        """Remove the tray icon."""
        if self._icon:
            self._icon.stop()
            logger.info("System tray icon stopped.")

    def set_tooltip(self, text: str) -> None:
        """Update the tray icon tooltip."""
        if self._icon:
            self._icon.title = text

    # ------------------------------------------------------------------

    def _run(self) -> None:
        img = _create_icon_image()

        menu = pystray.Menu(
            Item("Open Lcloud", self._open, default=True),
            pystray.Menu.SEPARATOR,
            Item("Quit", self._quit),
        )

        self._icon = pystray.Icon(
            name="lcloud",
            icon=img,
            title="Lcloud — Backup running",
            menu=menu,
        )
        self._icon.run()

    def _open(self, icon: pystray.Icon, item: Item) -> None:
        self._on_open()

    def _quit(self, icon: pystray.Icon, item: Item) -> None:
        self._on_quit()
        icon.stop()

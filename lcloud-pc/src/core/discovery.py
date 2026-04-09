"""
Lcloud PC App — Device Discovery
Registers the PC on the local network via mDNS so the Android app can find it,
and watches for the Android device advertising itself.
"""
import logging
import socket
import threading
from typing import Callable

from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf

from config import APP_NAME, PC_PORT, PC_SERVICE_NAME, SERVICE_TYPE

logger = logging.getLogger(__name__)


class _PhoneListener(ServiceListener):
    """Receives mDNS events when a phone announces or disappears."""

    def __init__(
        self,
        on_found: Callable[[str, str, int], None],
        on_lost: Callable[[str], None],
    ) -> None:
        self._on_found = on_found
        self._on_lost = on_lost

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info and name != PC_SERVICE_NAME:
            address = socket.inet_ntoa(info.addresses[0]) if info.addresses else "?"
            port = info.port
            logger.info("Phone found: %s @ %s:%s", name, address, port)
            self._on_found(name, address, port)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        if name != PC_SERVICE_NAME:
            logger.info("Phone lost: %s", name)
            self._on_lost(name)

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass  # Not needed for v0.1


class LcloudDiscovery:
    """
    Manages mDNS registration and browsing for Lcloud devices.

    Usage:
        discovery = LcloudDiscovery(on_phone_found=..., on_phone_lost=...)
        discovery.start()
        # ... app runs ...
        discovery.stop()
    """

    def __init__(
        self,
        on_phone_found: Callable[[str, str, int], None] | None = None,
        on_phone_lost: Callable[[str], None] | None = None,
        port: int = PC_PORT,
    ) -> None:
        self._port = port
        self._on_phone_found = on_phone_found or (lambda *_: None)
        self._on_phone_lost = on_phone_lost or (lambda *_: None)
        self._zeroconf: Zeroconf | None = None
        self._browser: ServiceBrowser | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Register PC on the network and start watching for Android devices."""
        with self._lock:
            if self._zeroconf:
                return  # Already running

            hostname = socket.gethostname()
            local_ip = self._local_ip()

            info = ServiceInfo(
                type_=SERVICE_TYPE,
                name=PC_SERVICE_NAME,
                addresses=[socket.inet_aton(local_ip)],
                port=self._port,
                properties={
                    b"version": APP_NAME.encode(),
                    b"platform": b"windows",
                },
                server=f"{hostname}.local.",
            )

            self._zeroconf = Zeroconf()
            self._zeroconf.register_service(info)
            logger.info("Registered PC as %s on %s:%s", PC_SERVICE_NAME, local_ip, self._port)

            listener = _PhoneListener(self._on_phone_found, self._on_phone_lost)
            self._browser = ServiceBrowser(self._zeroconf, SERVICE_TYPE, listener)
            logger.info("Listening for Android devices on mDNS...")

    def stop(self) -> None:
        """Unregister from the network and stop browsing."""
        with self._lock:
            if self._zeroconf:
                self._zeroconf.unregister_all_services()
                self._zeroconf.close()
                self._zeroconf = None
                self._browser = None
                logger.info("Discovery stopped.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _local_ip() -> str:
        """Get the machine's WiFi/LAN IP address (not 127.0.0.1)."""
        try:
            # Connect to a public address to find the default route interface
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"

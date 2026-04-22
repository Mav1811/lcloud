"""
Lcloud PC — Device Discovery (Multicast UDP)

Broadcasts the PC's presence on the local network every 2 seconds.
The Android app listens on the multicast group, parses the JSON payload,
and uses the included IP + fingerprint to connect via HTTPS.

No Bonjour / Zeroconf / mDNS required.
"""
import json
import logging
import socket
import threading
from typing import Callable

from config import MULTICAST_GROUP, MULTICAST_PORT, PROTOCOL_VERSION

logger = logging.getLogger(__name__)

_BROADCAST_INTERVAL = 2.0  # seconds between broadcasts


class LcloudDiscovery:
    """
    Broadcasts PC identity via multicast UDP.

    Usage:
        discovery = LcloudDiscovery(
            alias="MyPC",
            fingerprint="abc123...",
            port=53317,
        )
        discovery.start()
        # ... app runs ...
        discovery.stop()
    """

    def __init__(
        self,
        alias: str,
        fingerprint: str,
        port: int,
        on_phone_found: Callable[[str, str, int], None] | None = None,
        on_phone_lost: Callable[[str], None] | None = None,
    ) -> None:
        self._alias = alias
        self._fingerprint = fingerprint
        self._port = port
        # on_phone_found / on_phone_lost kept for API compatibility but unused —
        # phone now connects to us directly via HTTPS.
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start broadcasting in a daemon thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._broadcast_loop, daemon=True, name="lcloud-discovery"
        )
        self._thread.start()
        logger.info(
            "Discovery: broadcasting on %s:%s every %.0fs",
            MULTICAST_GROUP, MULTICAST_PORT, _BROADCAST_INTERVAL,
        )

    def stop(self) -> None:
        """Signal the broadcast thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        logger.info("Discovery stopped.")

    def _broadcast_loop(self) -> None:
        payload = json.dumps({
            "alias": self._alias,
            "version": PROTOCOL_VERSION,
            "deviceType": "desktop",
            "fingerprint": self._fingerprint,
            "port": self._port,
            "protocol": "https",
        }).encode()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)

        try:
            while not self._stop_event.is_set():
                try:
                    sock.sendto(payload, (MULTICAST_GROUP, MULTICAST_PORT))
                except OSError as exc:
                    logger.warning("Broadcast send failed: %s", exc)
                self._stop_event.wait(_BROADCAST_INTERVAL)
        finally:
            sock.close()

    @staticmethod
    def local_ip() -> str:
        """Return the machine's LAN IP (not loopback)."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"

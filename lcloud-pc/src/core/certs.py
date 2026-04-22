"""
Lcloud PC — TLS Certificate Manager

Generates and persists a self-signed RSA-2048 certificate for the HTTPS server.
On first run, creates cert + key files. On subsequent runs, loads existing ones.
"""
import datetime
import hashlib
import logging
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

logger = logging.getLogger(__name__)


def load_or_generate(cert_path: Path, key_path: Path) -> tuple[str, str]:
    """
    Load existing cert/key pair or generate a new one.

    Args:
        cert_path: Where to store / load the PEM certificate.
        key_path:  Where to store / load the PEM private key.

    Returns:
        (cert_pem, key_pem) as strings.
    """
    if cert_path.exists() and key_path.exists():
        logger.info("Loading TLS certificate from %s", cert_path)
        return (
            cert_path.read_text(encoding="utf-8"),
            key_path.read_text(encoding="utf-8"),
        )

    logger.info("Generating self-signed TLS certificate...")
    cert_path.parent.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "lcloud"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("lcloud")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode("utf-8")

    cert_path.write_text(cert_pem, encoding="utf-8")
    key_path.write_text(key_pem, encoding="utf-8")
    logger.info("Certificate saved to %s", cert_path)

    return cert_pem, key_pem


def get_fingerprint(cert_pem: str) -> str:
    """Return the SHA-256 fingerprint of the cert as a 64-char hex string."""
    cert = x509.load_pem_x509_certificate(cert_pem.encode())
    der = cert.public_bytes(serialization.Encoding.DER)
    return hashlib.sha256(der).hexdigest()

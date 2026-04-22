"""Tests for TLS certificate management."""
import hashlib
import sys
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.certs import get_fingerprint, load_or_generate


class TestLoadOrGenerate:
    def test_creates_cert_files_when_missing(self, tmp_path):
        cert_path = tmp_path / "lcloud.crt"
        key_path = tmp_path / "lcloud.key"
        cert_pem, key_pem = load_or_generate(cert_path, key_path)
        assert cert_path.exists()
        assert key_path.exists()
        assert "BEGIN CERTIFICATE" in cert_pem
        assert "PRIVATE KEY" in key_pem

    def test_returns_same_cert_on_reload(self, tmp_path):
        cert_path = tmp_path / "lcloud.crt"
        key_path = tmp_path / "lcloud.key"
        cert_pem1, _ = load_or_generate(cert_path, key_path)
        cert_pem2, _ = load_or_generate(cert_path, key_path)
        assert cert_pem1 == cert_pem2

    def test_generated_cert_is_valid_x509(self, tmp_path):
        cert_path = tmp_path / "lcloud.crt"
        key_path = tmp_path / "lcloud.key"
        cert_pem, _ = load_or_generate(cert_path, key_path)
        cert = x509.load_pem_x509_certificate(cert_pem.encode())
        assert cert.subject.get_attributes_for_oid(
            x509.oid.NameOID.COMMON_NAME
        )[0].value == "lcloud"


class TestGetFingerprint:
    def test_returns_64_char_hex_string(self, tmp_path):
        cert_path = tmp_path / "lcloud.crt"
        key_path = tmp_path / "lcloud.key"
        cert_pem, _ = load_or_generate(cert_path, key_path)
        fp = get_fingerprint(cert_pem)
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_fingerprint_is_stable(self, tmp_path):
        cert_path = tmp_path / "lcloud.crt"
        key_path = tmp_path / "lcloud.key"
        cert_pem, _ = load_or_generate(cert_path, key_path)
        assert get_fingerprint(cert_pem) == get_fingerprint(cert_pem)

    def test_fingerprint_is_sha256_of_der(self, tmp_path):
        cert_path = tmp_path / "lcloud.crt"
        key_path = tmp_path / "lcloud.key"
        cert_pem, _ = load_or_generate(cert_path, key_path)
        cert = x509.load_pem_x509_certificate(cert_pem.encode())
        der = cert.public_bytes(serialization.Encoding.DER)
        expected = hashlib.sha256(der).hexdigest()
        assert get_fingerprint(cert_pem) == expected

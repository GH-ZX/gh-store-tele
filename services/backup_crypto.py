"""Cryptographic and integrity utilities for GH Store database backups.

Provides authenticated AES-256-GCM encryption with PBKDF2 key derivation
and SHA-256 checksum manifest verification.
"""
from __future__ import annotations

import gzip
import hashlib
import os
import secrets
import struct
from pathlib import Path
from typing import Union

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTOGRAPHY = True
except ImportError:  # pragma: no cover
    AESGCM = None
    HAS_CRYPTOGRAPHY = False

MAGIC_HEADER = b"GHSTORE_ENC_V1\n"
SALT_LEN = 16
NONCE_LEN = 12
PBKDF2_ITERATIONS = 100_000


class BackupCryptoError(Exception):
    """Base exception for backup encryption / decryption errors."""
    pass


class BackupIntegrityError(BackupCryptoError):
    """Raised when checksum or authentication tag fails (data corrupted/tampered)."""
    pass


def derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from passphrase and salt using PBKDF2-HMAC-SHA256."""
    if not passphrase:
        raise BackupCryptoError("Passphrase / encryption key cannot be empty.")
    # If given exact 64-char hex key (32 bytes), use hex-decoded bytes if no salt needed,
    # or combine with salt for standard PBKDF2.
    return hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        iterations=PBKDF2_ITERATIONS,
        dklen=32,
    )


def compute_sha256(target: Union[bytes, str, Path]) -> str:
    """Compute hex SHA-256 hash of bytes or file contents."""
    hasher = hashlib.sha256()
    if isinstance(target, (str, Path)):
        p = Path(target)
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
    else:
        hasher.update(target)
    return hasher.hexdigest()


def write_sha256_manifest(archive_path: Path, digest: str | None = None) -> Path:
    """Write standard sha256sum manifest file alongside archive."""
    if digest is None:
        digest = compute_sha256(archive_path)
    manifest_path = archive_path.with_name(archive_path.name + ".sha256")
    manifest_path.write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8")
    return manifest_path


def verify_sha256_manifest(archive_path: Path) -> tuple[bool, str, str]:
    """Verify archive against its companion .sha256 file if present.

    Returns:
        (is_valid, calculated_hash, manifest_hash)
    """
    manifest_path = archive_path.with_name(archive_path.name + ".sha256")
    calculated = compute_sha256(archive_path)
    if not manifest_path.exists():
        return False, calculated, ""
    content = manifest_path.read_text(encoding="utf-8").strip()
    manifest_hash = content.split()[0] if content else ""
    return (calculated.lower() == manifest_hash.lower()), calculated, manifest_hash


def encrypt_payload(data: bytes, passphrase: str, compress: bool = True) -> bytes:
    """Compress with gzip (optional) and encrypt with AES-256-GCM.

    Format:
    [MAGIC_HEADER: 15B][salt_len: 1B][nonce_len: 1B][salt: 16B][nonce: 12B][ciphertext + 16B tag]
    """
    if not HAS_CRYPTOGRAPHY or AESGCM is None:
        raise BackupCryptoError("cryptography library is required for backup encryption.")
    if not passphrase:
        raise BackupCryptoError("Passphrase must be non-empty for encryption.")

    plaintext = gzip.compress(data) if compress else data
    salt = secrets.token_bytes(SALT_LEN)
    nonce = secrets.token_bytes(NONCE_LEN)
    key = derive_key(passphrase, salt)

    aesgcm = AESGCM(key)
    # Header serves as Authenticated Associated Data (AAD) preventing header tampering
    aad = MAGIC_HEADER
    ciphertext_and_tag = aesgcm.encrypt(nonce, plaintext, aad)

    header_lens = struct.pack("!BB", len(salt), len(nonce))
    return MAGIC_HEADER + header_lens + salt + nonce + ciphertext_and_tag


def decrypt_payload(blob: bytes, passphrase: str, decompress: bool = True) -> bytes:
    """Decrypt an AES-256-GCM backup payload and optionally decompress gzip."""
    if not HAS_CRYPTOGRAPHY or AESGCM is None:
        raise BackupCryptoError("cryptography library is required for backup decryption.")
    if not passphrase:
        raise BackupCryptoError("Passphrase must be provided to decrypt.")

    if not blob.startswith(MAGIC_HEADER):
        raise BackupCryptoError("Invalid backup format: missing GH Store encryption magic header.")

    offset = len(MAGIC_HEADER)
    salt_len, nonce_len = struct.unpack_from("!BB", blob, offset)
    offset += 2

    salt = blob[offset:offset + salt_len]
    offset += salt_len

    nonce = blob[offset:offset + nonce_len]
    offset += nonce_len

    ciphertext_and_tag = blob[offset:]

    key = derive_key(passphrase, salt)
    aesgcm = AESGCM(key)

    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext_and_tag, MAGIC_HEADER)
    except Exception as e:
        raise BackupIntegrityError(f"Decryption failed (incorrect key or corrupted payload): {e}") from e

    if decompress:
        try:
            return gzip.decompress(plaintext)
        except Exception as e:
            # If it wasn't gzipped, return raw plaintext
            return plaintext
    return plaintext

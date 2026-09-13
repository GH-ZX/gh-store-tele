"""Automated unit and regression tests for GH Store backup, encryption, and restore system."""
import gzip
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from services.backup_crypto import (
    MAGIC_HEADER,
    BackupCryptoError,
    BackupIntegrityError,
    compute_sha256,
    decrypt_payload,
    derive_key,
    encrypt_payload,
    verify_sha256_manifest,
    write_sha256_manifest,
)
from scripts.backup_db import rotate_old_backups
from scripts.restore_db import load_and_decrypt_sql


def test_derive_key_deterministic_and_unique():
    salt1 = b"0123456789abcdef"
    salt2 = b"fedcba9876543210"
    passphrase = "test_secure_passphrase"

    k1 = derive_key(passphrase, salt1)
    k1_again = derive_key(passphrase, salt1)
    k2 = derive_key(passphrase, salt2)

    assert len(k1) == 32
    assert k1 == k1_again
    assert k1 != k2


def test_derive_key_empty_fails():
    with pytest.raises(BackupCryptoError):
        derive_key("", b"salt")


def test_encrypt_decrypt_roundtrip():
    original_sql = b"-- Test Database Dump\nCREATE TABLE test (id SERIAL PRIMARY KEY, name TEXT);\nINSERT INTO test VALUES (1, 'val');"
    passphrase = "my_backup_encryption_passphrase_123"

    encrypted_blob = encrypt_payload(original_sql, passphrase, compress=True)
    assert encrypted_blob.startswith(MAGIC_HEADER)
    assert encrypted_blob != original_sql

    restored_sql = decrypt_payload(encrypted_blob, passphrase, decompress=True)
    assert restored_sql == original_sql


def test_decrypt_wrong_key_fails():
    original_sql = b"SELECT 1;"
    encrypted_blob = encrypt_payload(original_sql, "correct_key", compress=True)

    with pytest.raises(BackupIntegrityError):
        decrypt_payload(encrypted_blob, "wrong_key", decompress=True)


def test_tampered_payload_rejected():
    original_sql = b"SELECT 42;"
    encrypted_blob = bytearray(encrypt_payload(original_sql, "secret_key", compress=True))

    # Tamper with the ciphertext (last 10 bytes)
    encrypted_blob[-5] ^= 0xFF

    with pytest.raises(BackupIntegrityError):
        decrypt_payload(bytes(encrypted_blob), "secret_key", decompress=True)


def test_invalid_header_rejected():
    with pytest.raises(BackupCryptoError, match="missing GH Store encryption magic header"):
        decrypt_payload(b"NOT_A_VALID_HEADER_DATA", "key")


def test_sha256_manifest_write_and_verify(tmp_path: Path):
    test_file = tmp_path / "ghstore_backup_test.sql.gz.enc"
    test_file.write_bytes(b"sample encrypted backup content")

    manifest = write_sha256_manifest(test_file)
    assert manifest.exists()
    assert manifest.name == "ghstore_backup_test.sql.gz.enc.sha256"

    # Verify matching hash
    is_valid, calc_hash, exp_hash = verify_sha256_manifest(test_file)
    assert is_valid is True
    assert calc_hash == exp_hash
    assert len(calc_hash) == 64

    # Tamper with the file
    test_file.write_bytes(b"tampered content")
    is_valid_after_tamper, calc_after, _ = verify_sha256_manifest(test_file)
    assert is_valid_after_tamper is False
    assert calc_after != exp_hash


def test_rotate_old_backups(tmp_path: Path):
    # Create 5 dummy backup archives and manifests
    for i in range(5):
        arc = tmp_path / f"ghstore_backup_2026-09-0{i+1}_100000.sql.gz.enc"
        arc.write_bytes(b"data")
        man = tmp_path / f"ghstore_backup_2026-09-0{i+1}_100000.sql.gz.enc.sha256"
        man.write_bytes(b"hash")

    # Retention count of 3 should prune the oldest 2
    rotate_old_backups(tmp_path, retention_count=3)

    remaining_archives = sorted(tmp_path.glob("*.sql.gz.enc"))
    assert len(remaining_archives) == 3
    assert remaining_archives[0].name == "ghstore_backup_2026-09-03_100000.sql.gz.enc"
    assert remaining_archives[-1].name == "ghstore_backup_2026-09-05_100000.sql.gz.enc"

    # Oldest manifests should also be pruned
    assert not (tmp_path / "ghstore_backup_2026-09-01_100000.sql.gz.enc.sha256").exists()
    assert not (tmp_path / "ghstore_backup_2026-09-02_100000.sql.gz.enc.sha256").exists()
    assert (tmp_path / "ghstore_backup_2026-09-05_100000.sql.gz.enc.sha256").exists()


def test_load_and_decrypt_sql_plain_gzip(tmp_path: Path):
    test_sql = b"SELECT * FROM items;"
    gz_file = tmp_path / "ghstore_backup_plain.sql.gz"
    gz_file.write_bytes(gzip.compress(test_sql))

    loaded = load_and_decrypt_sql(gz_file)
    assert loaded == test_sql


def test_load_and_decrypt_sql_encrypted(tmp_path: Path):
    test_sql = b"SELECT * FROM users;"
    key = "test_key_abc"
    enc_blob = encrypt_payload(test_sql, key, compress=True)

    enc_file = tmp_path / "ghstore_backup_enc.sql.gz.enc"
    enc_file.write_bytes(enc_blob)
    write_sha256_manifest(enc_file)

    loaded = load_and_decrypt_sql(enc_file, passphrase=key)
    assert loaded == test_sql


def test_load_and_decrypt_sql_tampered_manifest_fails(tmp_path: Path):
    enc_file = tmp_path / "ghstore_backup_bad.sql.gz.enc"
    enc_file.write_bytes(b"original data")
    manifest = tmp_path / "ghstore_backup_bad.sql.gz.enc.sha256"
    manifest.write_text("0000000000000000000000000000000000000000000000000000000000000000  file\n")

    with pytest.raises(BackupIntegrityError, match="SHA-256 Checksum mismatch"):
        load_and_decrypt_sql(enc_file)


@pytest.mark.asyncio
async def test_run_database_backup_service(tmp_path: Path, monkeypatch):
    from services.backup_service import run_database_backup
    import config

    # Mock backup script execution
    async def fake_communicate():
        return (b"Backup created successfully", b"")

    fake_proc = AsyncMock()
    fake_proc.communicate = fake_communicate
    fake_proc.returncode = 0

    mock_bot = AsyncMock()
    mock_bot.send_document = AsyncMock()

    monkeypatch.setattr(config, "BACKUP_CHANNEL_ID", "-100123456789")

    # Create dummy backup file in backups dir
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    sample_backup = backup_dir / "ghstore_backup_2026-09-13_120000.sql.gz.enc"
    sample_backup.write_bytes(b"encrypted_content")
    write_sha256_manifest(sample_backup)

    with patch("asyncio.create_subprocess_exec", return_value=fake_proc), \
         patch("services.backup_service.ROOT", tmp_path), \
         patch.dict("sys.modules", {"bot": type("BotModule", (), {"bot": mock_bot})}):

        success = await run_database_backup()
        assert success is True
        assert mock_bot.send_document.called
        call_kwargs = mock_bot.send_document.call_args.kwargs
        assert call_kwargs["chat_id"] == "-100123456789"
        assert "AES-256-GCM Encrypted" in call_kwargs["caption"]
        assert "ghstore_backup_2026-09-13_120000.sql.gz.enc" in call_kwargs["caption"]

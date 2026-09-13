#!/usr/bin/env python3
"""Automated Database Restoration & Verification Tool for GH Store.

Features:
- Verifies SHA-256 checksum against companion .sha256 manifest.
- Decrypts AES-256-GCM authenticated encrypted archives (.sql.gz.enc).
- Decompresses gzip streams (.sql.gz).
- Supports --verify-only mode to audit integrity without modifying the database.
- Supports --decrypt-only mode to extract plain SQL for inspection.
- Safely prompts for confirmation before applying changes to target database.
- Restores via local psql or via running PostgreSQL container (docker exec).

Usage:
    # Verify backup integrity without restoring:
    python scripts/restore_db.py backups/ghstore_backup_2026-09-13_110000.sql.gz.enc --verify-only

    # Decrypt to plain SQL file:
    python scripts/restore_db.py backups/ghstore_backup_2026-09-13_110000.sql.gz.enc --decrypt-only -o restored.sql

    # Restore to database (interactive confirmation required):
    python scripts/restore_db.py backups/ghstore_backup_2026-09-13_110000.sql.gz.enc

    # Restore non-interactively:
    python scripts/restore_db.py backups/ghstore_backup_2026-09-13_110000.sql.gz.enc --force
"""
from __future__ import annotations

import argparse
import gzip
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.backup_crypto import (
    MAGIC_HEADER,
    BackupCryptoError,
    BackupIntegrityError,
    compute_sha256,
    decrypt_payload,
    verify_sha256_manifest,
)

try:
    import config
except ImportError:
    config = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GH Store PostgreSQL Backup Restoration Tool")
    parser.add_argument("backup_file", type=Path, help="Path to the backup file (.sql, .sql.gz, or .sql.gz.enc)")
    parser.add_argument("--key", help="Decryption key / passphrase override")
    parser.add_argument("--verify-only", action="store_true", help="Verify checksum and decryption without restoring")
    parser.add_argument("--decrypt-only", action="store_true", help="Decrypt and decompress to SQL file without restoring")
    parser.add_argument("-o", "--output", type=Path, help="Output path for --decrypt-only")
    parser.add_argument("-f", "--force", action="store_true", help="Bypass confirmation prompt")
    parser.add_argument("--db-user", help="Target database user override")
    parser.add_argument("--db-name", help="Target database name override")
    parser.add_argument("--db-host", help="Target database host override")
    parser.add_argument("--db-port", help="Target database port override")
    return parser.parse_args()


def get_psql_command(db_user: str, db_name: str, db_host: str, db_port: str, db_pass: str) -> list[str]:
    """Find the best available psql command (host binary, container binary, or docker exec)."""
    psql_bin = shutil.which("psql")
    if psql_bin:
        return [psql_bin, "-h", db_host, "-p", str(db_port), "-U", db_user, "-d", db_name]

    if shutil.which("docker"):
        return [
            "docker", "exec", "-i",
            "-e", f"PGPASSWORD={db_pass}",
            "GHstore-postgres",
            "psql", "-U", db_user, "-d", db_name,
        ]

    raise RuntimeError("Neither 'psql' nor 'docker' is available to execute database restoration.")


def load_and_decrypt_sql(backup_path: Path, passphrase: str | None = None) -> bytes:
    """Load backup file, verify integrity, decrypt and decompress to raw SQL bytes."""
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    # Step 1: Checksum verification if companion .sha256 exists
    manifest_path = backup_path.with_name(backup_path.name + ".sha256")
    if manifest_path.exists():
        is_valid, calc_hash, exp_hash = verify_sha256_manifest(backup_path)
        if not is_valid:
            raise BackupIntegrityError(
                f"SHA-256 Checksum mismatch for {backup_path.name}!\n"
                f"  Expected: {exp_hash}\n"
                f"  Computed: {calc_hash}"
            )
        print(f"[✓] SHA-256 Checksum verified: {calc_hash}")
    else:
        calc_hash = compute_sha256(backup_path)
        print(f"[*] Notice: No companion .sha256 manifest found. Computed SHA-256: {calc_hash}")

    raw_bytes = backup_path.read_bytes()
    if not raw_bytes:
        raise ValueError("Backup archive is empty (0 bytes).")

    # Step 2: Decryption if encrypted
    if raw_bytes.startswith(MAGIC_HEADER):
        key = passphrase or os.environ.get("BACKUP_ENCRYPTION_KEY") or (getattr(config, "BACKUP_ENCRYPTION_KEY", "") if config else "")
        if not key:
            raise BackupCryptoError(
                f"Backup file '{backup_path.name}' is encrypted with AES-256-GCM. "
                f"Please provide the decryption key via --key or BACKUP_ENCRYPTION_KEY env var."
            )
        print("[*] Decrypting AES-256-GCM authenticated payload...")
        sql_bytes = decrypt_payload(raw_bytes, key, decompress=True)
        print("[✓] Decryption and decompression successful.")
        return sql_bytes

    # Step 3: Plain Gzip compression (magic \x1f\x8b)
    if raw_bytes.startswith(b"\x1f\x8b"):
        print("[*] Decompressing gzip archive...")
        sql_bytes = gzip.decompress(raw_bytes)
        print("[✓] Decompression successful.")
        return sql_bytes

    # Step 4: Raw uncompressed SQL
    return raw_bytes


def main() -> int:
    print("\n=== GH Store Database Restoration Tool ===")
    args = parse_args()
    backup_path = args.backup_file.resolve()

    try:
        sql_bytes = load_and_decrypt_sql(backup_path, args.key)
    except Exception as e:
        print(f"[!] Error reading/decrypting backup: {e}")
        return 1

    size_kb = len(sql_bytes) / 1024
    print(f"[*] Prepared SQL payload: {size_kb:.1f} KB ({len(sql_bytes):,} bytes)")

    # Verify-only mode
    if args.verify_only:
        print("[✓] Backup archive verified successfully. Integrity check PASSED.")
        return 0

    # Decrypt-only mode
    if args.decrypt_only:
        out_path = args.output or backup_path.with_name(backup_path.stem.replace(".sql.gz", "") + "_decrypted.sql")
        out_path.write_bytes(sql_bytes)
        print(f"[✓] Plain SQL extracted to: {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")
        return 0

    # Database restore mode
    db_user = args.db_user or os.environ.get("POSTGRES_USER", getattr(config, "DB_USER", "postgres") if config else "postgres")
    db_name = args.db_name or os.environ.get("POSTGRES_DB", getattr(config, "DB_NAME", "ghstore") if config else "ghstore")
    db_host = args.db_host or os.environ.get("DB_HOST", getattr(config, "DB_HOST", "localhost") if config else "localhost")
    db_port = args.db_port or os.environ.get("DB_PORT", getattr(config, "DB_PORT", "5432") if config else "5432")
    db_pass = os.environ.get("POSTGRES_PASSWORD", getattr(config, "DB_PASS", "") if config else "")

    print("\n⚠️  TARGET DATABASE CONFIGURATION:")
    print(f"    Host:     {db_host}:{db_port}")
    print(f"    Database: {db_name}")
    print(f"    User:     {db_user}")

    if not args.force:
        print("\n⚠️  WARNING: Restoring will overwrite existing data in the target database!")
        try:
            confirm = input("Type 'YES' to proceed with restoration: ")
        except (EOFError, KeyboardInterrupt):
            print("\n[!] Restoration aborted by user.")
            return 1
        if confirm.strip() != "YES":
            print("[!] Restoration aborted (confirmation mismatch).")
            return 1

    env = os.environ.copy()
    if db_pass:
        env["PGPASSWORD"] = db_pass

    try:
        cmd = get_psql_command(db_user, db_name, db_host, db_port, db_pass)
        print(f"[*] Executing SQL restore via {' '.join(cmd[:2])}...")

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        stdout_data, stderr_data = proc.communicate(input=sql_bytes)

        if proc.returncode != 0:
            err_msg = stderr_data.decode(errors="replace")
            print(f"[!] Database restoration failed (code {proc.returncode}):\n{err_msg}")
            return proc.returncode

        print(f"[✓] Database successfully restored from {backup_path.name}!")
        return 0

    except Exception as e:
        print(f"[!] Restoration execution error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Automated Authenticated & Encrypted PostgreSQL Database Backup Tool.

Features:
- Dumps PostgreSQL using pg_dump (native or dockerized).
- Compresses with gzip.
- Encrypts using military-grade authenticated AES-256-GCM when BACKUP_ENCRYPTION_KEY is set.
- Generates SHA-256 checksum manifest (.sha256) alongside the archive.
- Retains rotating local backups (keeps last N daily archives).
- Supports streaming encrypted backups and checksums to Cloudflare R2 / AWS S3.
- Can be run as a standalone CLI or scheduled via cron / systemd.

Usage:
    python scripts/backup_db.py [--key <secret>] [--output <path>] [--retention <n>] [--no-encrypt]
"""
from __future__ import annotations

import argparse
import datetime
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Add project root to sys.path so config and services can be imported
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.backup_crypto import (
    BackupCryptoError,
    compute_sha256,
    encrypt_payload,
    write_sha256_manifest,
)

try:
    import config
except ImportError:
    config = None

BACKUP_DIR = ROOT / "backups"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GH Store PostgreSQL Backup Tool")
    parser.add_argument("-o", "--output", help="Custom destination backup file path")
    parser.add_argument("--key", help="Encryption key / passphrase override")
    parser.add_argument("--no-encrypt", action="store_true", help="Disable encryption even if key is present")
    parser.add_argument(
        "--retention",
        type=int,
        default=getattr(config, "BACKUP_RETENTION_DAYS", 14) if config else 14,
        help="Number of backup archives to retain (default: 14)",
    )
    return parser.parse_args()


def get_pg_dump_command(db_user: str, db_name: str, db_host: str, db_port: str, db_pass: str) -> list[str]:
    """Find the best available pg_dump command (host binary, container binary, or docker exec)."""
    pg_dump_bin = shutil.which("pg_dump")
    if pg_dump_bin:
        return [pg_dump_bin, "-h", db_host, "-p", str(db_port), "-U", db_user, db_name]

    # Check for docker
    if shutil.which("docker"):
        return [
            "docker", "exec",
            "-e", f"PGPASSWORD={db_pass}",
            "GHstore-postgres",
            "pg_dump", "-U", db_user, db_name,
        ]

    raise RuntimeError("Neither 'pg_dump' nor 'docker' is available in the environment.")


def execute_backup(
    output_path: Path | None = None,
    encryption_key: str | None = None,
    no_encrypt: bool = False,
    retention: int = 14,
) -> tuple[int, Path | None, str]:
    """Execute the database dump, compression, optional encryption, and rotation.

    Returns:
        (exit_code, backup_file_path, sha256_digest)
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    db_user = os.environ.get("POSTGRES_USER", getattr(config, "DB_USER", "postgres") if config else "postgres")
    db_name = os.environ.get("POSTGRES_DB", getattr(config, "DB_NAME", "ghstore") if config else "ghstore")
    db_host = os.environ.get("DB_HOST", getattr(config, "DB_HOST", "localhost") if config else "localhost")
    db_port = os.environ.get("DB_PORT", getattr(config, "DB_PORT", "5432") if config else "5432")
    db_pass = os.environ.get("POSTGRES_PASSWORD", getattr(config, "DB_PASS", "") if config else "")

    key = encryption_key or os.environ.get("BACKUP_ENCRYPTION_KEY") or (getattr(config, "BACKUP_ENCRYPTION_KEY", "") if config else "")
    should_encrypt = bool(key and not no_encrypt)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    ext = ".sql.gz.enc" if should_encrypt else ".sql.gz"

    if output_path:
        dest_path = Path(output_path)
    else:
        dest_path = BACKUP_DIR / f"ghstore_backup_{timestamp}{ext}"

    env = os.environ.copy()
    if db_pass:
        env["PGPASSWORD"] = db_pass

    print(f"[*] Dumping database '{db_name}' from {db_host}:{db_port}...")
    try:
        cmd = get_pg_dump_command(db_user, db_name, db_host, db_port, db_pass)
        dump_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        stdout_data, stderr_data = dump_proc.communicate()

        if dump_proc.returncode != 0:
            err_msg = stderr_data.decode(errors="replace")
            print(f"[!] pg_dump failed (code {dump_proc.returncode}): {err_msg}")
            return 1, None, ""

        raw_sql = stdout_data
        if not raw_sql:
            print("[!] Dump produced empty output.")
            return 1, None, ""

        if should_encrypt:
            print("[*] Encrypting and compressing archive using AES-256-GCM...")
            final_bytes = encrypt_payload(raw_sql, key, compress=True)
        else:
            import gzip
            print("[!] Notice: Encryption key not configured; compressing with gzip only.")
            final_bytes = gzip.compress(raw_sql)

        dest_path.write_bytes(final_bytes)
        digest = compute_sha256(final_bytes)
        manifest_path = write_sha256_manifest(dest_path, digest)

        size_kb = dest_path.stat().st_size / 1024
        enc_label = "🔒 AES-256-GCM Encrypted" if should_encrypt else "📦 Gzip Compressed"
        print(f"[✓] Backup created successfully: {dest_path.name} ({size_kb:.1f} KB) [{enc_label}]")
        print(f"[✓] SHA-256 Checksum: {digest}")
        print(f"[✓] Manifest saved: {manifest_path.name}")

    except Exception as e:
        print(f"[!] Backup failed: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return 1, None, ""

    # Rotate old backups (keep last N)
    rotate_old_backups(BACKUP_DIR, retention)

    # Cloudflare R2 / S3 upload if configured
    upload_to_remote_storage(dest_path, manifest_path)

    return 0, dest_path, digest


def rotate_old_backups(backup_dir: Path, retention_count: int) -> None:
    """Keep the last N backup files and prune older files and their manifests."""
    if retention_count <= 0:
        return

    # Look for archives matching ghstore_backup_*.sql.gz* (excluding .sha256)
    all_archives = sorted(
        [
            p for p in backup_dir.glob("ghstore_backup_*")
            if not p.name.endswith(".sha256") and (p.name.endswith(".gz") or p.name.endswith(".enc"))
        ],
        key=lambda p: p.stat().st_mtime,
    )

    if len(all_archives) > retention_count:
        to_prune = all_archives[:-retention_count]
        for old_file in to_prune:
            print(f"[*] Rotating out old archive: {old_file.name}")
            try:
                old_file.unlink(missing_ok=True)
                manifest = old_file.with_name(old_file.name + ".sha256")
                manifest.unlink(missing_ok=True)
            except Exception as e:
                print(f"[!] Failed to delete {old_file.name}: {e}")


def upload_to_remote_storage(archive_path: Path, manifest_path: Path) -> None:
    """Stream archive and manifest to Cloudflare R2 / AWS S3 if configured."""
    r2_bucket = os.environ.get("R2_BUCKET") or os.environ.get("S3_BUCKET")
    if not r2_bucket:
        return

    try:
        import boto3
        s3 = boto3.client(
            "s3",
            endpoint_url=os.environ.get("R2_ENDPOINT"),
            aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"),
        )
        s3.upload_file(str(archive_path), r2_bucket, f"backups/{archive_path.name}")
        if manifest_path.exists():
            s3.upload_file(str(manifest_path), r2_bucket, f"backups/{manifest_path.name}")
        print(f"[✓] Archive streamed to R2 bucket: {r2_bucket}/backups/{archive_path.name}")
    except Exception as e:
        print(f"[!] Cloudflare R2 / S3 upload skipped: {e}")


def main() -> int:
    print("\n=== GH Store Database Backup Tool ===")
    args = parse_args()
    code, _, _ = execute_backup(
        output_path=Path(args.output) if args.output else None,
        encryption_key=args.key,
        no_encrypt=args.no_encrypt,
        retention=args.retention,
    )
    if code == 0:
        print("[✓] Backup process completed successfully.")
    return code


if __name__ == "__main__":
    sys.exit(main())

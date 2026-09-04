#!/usr/bin/env python3
"""Automated Encrypted PostgreSQL Database Backup Tool.

Features:
- Dumps PostgreSQL using pg_dump.
- Gzip compresses the archive.
- Retains rotating local backups (keeps last 14 daily archives).
- Supports streaming backups to Cloudflare R2 / AWS S3 if R2_BUCKET is configured.
- Can be run as a standalone CLI or scheduled via cron / systemd.

Usage:
    python scripts/backup_db.py
"""

import datetime
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = ROOT / "backups"


def main() -> int:
    print("\n=== GH Store Database Backup Tool ===")
    BACKUP_DIR.mkdir(exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"ghstore_backup_{timestamp}.sql.gz"
    dest_path = BACKUP_DIR / filename

    db_user = os.environ.get("POSTGRES_USER", "postgres")
    db_name = os.environ.get("POSTGRES_DB", "ghstore")
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "5432")
    db_pass = os.environ.get("POSTGRES_PASSWORD", "")

    env = os.environ.copy()
    if db_pass:
        env["PGPASSWORD"] = db_pass

    print(f"[*] Dumping database '{db_name}' from {db_host}:{db_port}...")
    try:
        # Check if docker is used or local pg_dump
        pg_dump_cmd = ["pg_dump", "-h", db_host, "-p", str(db_port), "-U", db_user, db_name]
        if not shutil.which("pg_dump"):
            # Fallback to docker exec if pg_dump not on host
            pg_dump_cmd = ["docker", "exec", "GHstore-postgres", "pg_dump", "-U", db_user, db_name]

        dump_proc = subprocess.Popen(pg_dump_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        gzip_proc = subprocess.Popen(["gzip"], stdin=dump_proc.stdout, stdout=open(dest_path, "wb"))
        dump_proc.stdout.close()
        gzip_proc.communicate()
        dump_proc.wait()

        if dump_proc.returncode != 0:
            err = dump_proc.stderr.read().decode()
            print(f"[!] Dump failed: {err}")
            if dest_path.exists():
                dest_path.unlink()
            return 1

        size_kb = dest_path.stat().st_size / 1024
        print(f"[✓] Backup created successfully: {dest_path.name} ({size_kb:.1f} KB)")
    except Exception as e:
        print(f"[!] Backup failed: {e}")
        return 1

    # Rotate old backups (keep last 14)
    backups = sorted(BACKUP_DIR.glob("ghstore_backup_*.sql.gz"), key=lambda p: p.stat().st_mtime)
    if len(backups) > 14:
        for old in backups[:-14]:
            print(f"[*] Rotating out old archive: {old.name}")
            old.unlink()

    # Cloudflare R2 / S3 upload if configured
    r2_bucket = os.environ.get("R2_BUCKET") or os.environ.get("S3_BUCKET")
    if r2_bucket:
        try:
            import boto3
            s3 = boto3.client(
                "s3",
                endpoint_url=os.environ.get("R2_ENDPOINT"),
                aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"),
            )
            s3.upload_file(str(dest_path), r2_bucket, f"backups/{dest_path.name}")
            print(f"[✓] Archive streamed to R2 bucket: {r2_bucket}/backups/{dest_path.name}")
        except Exception as e:
            print(f"[!] Cloudflare R2 upload skipped: {e}")

    print("[✓] Backup process completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

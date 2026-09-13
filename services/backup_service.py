"""Automated Database Backup Service & Retention Cron."""
import asyncio
import logging
import subprocess
import sys
import os
from pathlib import Path
import config

ROOT = Path(__file__).resolve().parent.parent
BACKUP_SCRIPT = ROOT / "scripts" / "backup_db.py"


async def run_database_backup() -> bool:
    """Run the database backup and rotation script asynchronously."""
    if not BACKUP_SCRIPT.exists():
        logging.error("Backup script not found: %s", BACKUP_SCRIPT)
        return False
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(BACKUP_SCRIPT),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            logging.info("Database backup completed successfully:\n%s", stdout.decode()[-300:])
            backup_channel = getattr(config, "BACKUP_CHANNEL_ID", None) or os.environ.get("BACKUP_CHANNEL_ID")
            if backup_channel:
                try:
                    from bot import bot
                    from aiogram.types import FSInputFile
                    backups = sorted(
                        [
                            p for p in (ROOT / "backups").glob("ghstore_backup_*")
                            if not p.name.endswith(".sha256") and (p.name.endswith(".gz") or p.name.endswith(".enc"))
                        ],
                        key=lambda p: p.stat().st_mtime,
                    )
                    if backups:
                        latest = backups[-1]
                        doc = FSInputFile(str(latest), filename=latest.name)
                        manifest = latest.with_name(latest.name + ".sha256")
                        sha_digest = manifest.read_text(encoding="utf-8").split()[0] if manifest.exists() else "N/A"
                        enc_status = "AES-256-GCM Encrypted" if latest.name.endswith(".enc") else "Gzip Compressed"
                        caption = (
                            f"🔒 <b>Automated Database Backup</b>\n\n"
                            f"• <b>Archive:</b> <code>{latest.name}</code>\n"
                            f"• <b>Security:</b> {enc_status}\n"
                            f"• <b>SHA-256:</b> <code>{sha_digest}</code>\n"
                            f"• <b>Size:</b> {latest.stat().st_size / 1024:.1f} KB"
                        )
                        await bot.send_document(chat_id=backup_channel, document=doc, caption=caption, parse_mode="HTML")
                        logging.info("Database backup streamed to Telegram backup channel %s", backup_channel)
                except Exception as e:
                    logging.warning("Could not stream backup to Telegram channel: %s", e)
            return True
        else:
            logging.error("Database backup failed (code %s):\n%s", proc.returncode, stderr.decode()[-300:])
            return False
    except Exception as e:
        logging.error("Failed to execute database backup: %s", e)
        return False


async def periodic_backup_cron() -> None:
    """Periodic backup runner executing every 24 hours."""
    from services.distributed_lock import leader_lease
    # Initial sleep of 5 minutes after startup so boot is fast
    await asyncio.sleep(300)
    while True:
        async with leader_lease("periodic_backup_cron", ttl_seconds=86400) as is_leader:
            if is_leader:
                try:
                    await run_database_backup()
                except Exception as e:
                    logging.warning("Backup cron error: %s", e)
        await asyncio.sleep(86400)

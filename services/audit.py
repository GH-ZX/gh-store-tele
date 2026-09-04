import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from db import session_commit
from models.admin_audit_log import AdminAuditLog


class AuditService:

    @staticmethod
    async def log(admin_tg_id: int, action: str, details: dict | None = None,
                  ip_address: str | None = None, session: AsyncSession | Session | None = None) -> None:
        """Record an administrative action into the audit log."""
        try:
            from db import get_db_session
            if session is None:
                async with get_db_session() as s:
                    entry = AdminAuditLog(
                        admin_tg_id=admin_tg_id,
                        action=action,
                        details=details,
                        ip_address=ip_address,
                    )
                    s.add(entry)
                    await session_commit(s)
            else:
                entry = AdminAuditLog(
                    admin_tg_id=admin_tg_id,
                    action=action,
                    details=details,
                    ip_address=ip_address,
                )
                session.add(entry)
                await session_commit(session)
        except Exception as e:
            logging.error("Failed to write audit log: %s", e)

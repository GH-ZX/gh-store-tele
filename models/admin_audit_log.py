import datetime
from pydantic import BaseModel
from sqladmin import ModelView
from sqlalchemy import Column, Integer, BigInteger, Text, DateTime, JSON

from models.base import Base


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True)
    admin_tg_id = Column(BigInteger, nullable=False, index=True)
    action = Column(Text, nullable=False, index=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)

    def __repr__(self):
        return f"AdminAuditLog admin={self.admin_tg_id} action={self.action}"


class AdminAuditLogDTO(BaseModel):
    id: int | None = None
    admin_tg_id: int
    action: str
    details: dict | None = None
    ip_address: str | None = None
    created_at: datetime.datetime | None = None


class AdminAuditLogAdmin(ModelView, model=AdminAuditLog):
    name = "Audit Log"
    name_plural = "Audit Logs"
    icon = "fa-solid fa-clipboard-list"
    category = "Administration"

    column_list = [
        AdminAuditLog.id,
        AdminAuditLog.admin_tg_id,
        AdminAuditLog.action,
        AdminAuditLog.details,
        AdminAuditLog.ip_address,
        AdminAuditLog.created_at,
    ]
    column_searchable_list = [AdminAuditLog.action, AdminAuditLog.ip_address]
    column_sortable_list = [AdminAuditLog.id, AdminAuditLog.created_at]
    can_create = False
    can_edit = False
    can_delete = False
    can_export = True

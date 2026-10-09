"""Модель транзакционного outbox."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, enum_column
from app.models.enums import OutboxStatus


class OutboxMessage(Base, TimestampMixin):
    """Событие, записанное в одной транзакции с изменением предметной сущности.

    Публикацией в брокер занимается отдельный воркер (`app.outbox.publisher`),
    поэтому событие не теряется, даже если RabbitMQ недоступен в момент запроса.
    """

    __tablename__ = "outbox"
    __table_args__ = (
        Index("ix_outbox_dispatch", "status", "available_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    aggregate_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)

    exchange: Mapped[str] = mapped_column(String(255), nullable=False)
    routing_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    status: Mapped[OutboxStatus] = mapped_column(
        enum_column(OutboxStatus, "outbox_status"),
        nullable=False,
        default=OutboxStatus.PENDING,
    )
    attempts: Mapped[int] = mapped_column(nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<OutboxMessage id={self.id} event={self.event_type} status={self.status}>"

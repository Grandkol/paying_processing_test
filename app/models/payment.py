"""Модель платежа."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Index, Numeric, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, enum_column
from app.models.enums import Currency, PaymentStatus


class Payment(Base, TimestampMixin):
    """Платёж — основная сущность сервиса.

    Атрибут `payment_metadata` отображается на столбец `metadata`: имя `metadata`
    в декларативном классе занято самой SQLAlchemy.
    """

    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(enum_column(Currency, "currency"), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    payment_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    status: Mapped[PaymentStatus] = mapped_column(
        enum_column(PaymentStatus, "payment_status"),
        nullable=False,
        default=PaymentStatus.PENDING,
    )

    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    webhook_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    webhook_attempts: Mapped[int] = mapped_column(nullable=False, default=0)
    webhook_delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Payment id={self.id} status={self.status} amount={self.amount} {self.currency}>"

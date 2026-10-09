"""Доступ к таблице payments."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PaymentStatus
from app.models.payment import Payment


class PaymentRepository:
    """Репозиторий платежей. Транзакцией управляет вызывающий код."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, payment: Payment) -> None:
        self._session.add(payment)

    async def get(self, payment_id: uuid.UUID) -> Payment | None:
        return await self._session.get(Payment, payment_id)

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        result = await self._session.execute(
            select(Payment).where(Payment.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def finalize(self, payment_id: uuid.UUID, status: PaymentStatus) -> bool:
        """Переводит платёж из pending в терминальный статус.

        Условие `status == PENDING` в WHERE делает операцию идемпотентной: повторная
        доставка того же события (или гонка двух consumer-ов) не перезапишет результат.
        Возвращает False, если платёж уже обработан.
        """
        result = await self._session.execute(
            update(Payment)
            .where(Payment.id == payment_id, Payment.status == PaymentStatus.PENDING)
            .values(status=status, processed_at=datetime.now(UTC))
            .returning(Payment.id)
        )
        return result.scalar_one_or_none() is not None

    async def register_webhook_attempt(self, payment_id: uuid.UUID) -> None:
        """Увеличивает счётчик попыток доставки webhook."""
        await self._session.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(webhook_attempts=Payment.webhook_attempts + 1)
        )

    async def mark_webhook_delivered(self, payment_id: uuid.UUID) -> None:
        await self._session.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(webhook_delivered_at=datetime.now(UTC))
        )

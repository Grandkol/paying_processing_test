"""Доступ к таблице outbox."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OutboxStatus
from app.models.outbox import OutboxMessage


class OutboxRepository:
    """Репозиторий событий outbox. Транзакцией управляет вызывающий код."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(
        self,
        *,
        message_id: uuid.UUID,
        aggregate_id: uuid.UUID,
        event_type: str,
        exchange: str,
        routing_key: str,
        payload: dict[str, Any],
    ) -> OutboxMessage:
        message = OutboxMessage(
            id=message_id,
            aggregate_id=aggregate_id,
            event_type=event_type,
            exchange=exchange,
            routing_key=routing_key,
            payload=payload,
            status=OutboxStatus.PENDING,
            available_at=datetime.now(UTC),
        )
        self._session.add(message)
        return message

    async def claim_batch(self, limit: int) -> list[OutboxMessage]:
        """Забирает пачку готовых к публикации событий.

        `FOR UPDATE SKIP LOCKED` позволяет запускать несколько публикаторов параллельно:
        каждый берёт свои строки и не ждёт чужих блокировок. Блокировка держится до
        конца транзакции, то есть до фиксации результата публикации.
        """
        result = await self._session.execute(
            select(OutboxMessage)
            .where(
                OutboxMessage.status == OutboxStatus.PENDING,
                OutboxMessage.available_at <= datetime.now(UTC),
            )
            .order_by(OutboxMessage.available_at, OutboxMessage.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    @staticmethod
    def mark_published(message: OutboxMessage) -> None:
        message.status = OutboxStatus.PUBLISHED
        message.published_at = datetime.now(UTC)
        message.attempts += 1
        message.last_error = None

    @staticmethod
    def mark_attempt_failed(
        message: OutboxMessage,
        error: str,
        *,
        max_attempts: int,
        base_delay: float,
    ) -> None:
        """Планирует повторную публикацию с экспоненциальной задержкой."""
        message.attempts += 1
        message.last_error = error[:2000]
        if message.attempts >= max_attempts:
            message.status = OutboxStatus.FAILED
            return
        delay = base_delay * (2 ** (message.attempts - 1))
        message.available_at = datetime.now(UTC) + timedelta(seconds=delay)

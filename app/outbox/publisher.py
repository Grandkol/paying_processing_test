"""Воркер-публикатор транзакционного outbox."""

import asyncio
import contextlib
import logging

from faststream.rabbit import RabbitBroker
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.broker.topology import HEADER_RETRY_COUNT, resolve_exchange
from app.core.config import settings
from app.repositories.outbox import OutboxRepository

logger = logging.getLogger(__name__)


class OutboxPublisher:
    """Перекладывает события из таблицы `outbox` в RabbitMQ.

    Доставка — at-least-once. Сообщение считается опубликованным после подтверждения
    брокера (publisher confirms), и только затем в БД фиксируется статус. Если процесс
    упадёт между подтверждением и COMMIT, событие опубликуется второй раз, поэтому
    consumer сделан идемпотентным.
    """

    def __init__(
        self,
        broker: RabbitBroker,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        batch_size: int = settings.outbox_batch_size,
        poll_interval: float = settings.outbox_poll_interval,
        max_attempts: int = settings.outbox_max_attempts,
        retry_base_delay: float = settings.outbox_retry_base_delay,
    ) -> None:
        self._broker = broker
        self._session_factory = session_factory
        self._batch_size = batch_size
        self._poll_interval = poll_interval
        self._max_attempts = max_attempts
        self._retry_base_delay = retry_base_delay
        self._stop_event = asyncio.Event()

    def stop(self) -> None:
        """Просит воркер завершиться после текущей пачки."""
        self._stop_event.set()

    async def run_forever(self) -> None:
        logger.info(
            "Outbox-публикатор запущен (пачка=%s, интервал=%.2f с)",
            self._batch_size,
            self._poll_interval,
        )
        while not self._stop_event.is_set():
            try:
                published = await self.publish_pending()
            except Exception:
                logger.exception(
                    "Сбой цикла публикации outbox, повтор через %s с", self._poll_interval
                )
                published = 0

            if published >= self._batch_size:
                continue
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._poll_interval)

        logger.info("Outbox-публикатор остановлен")

    async def publish_pending(self) -> int:
        """Публикует одну пачку событий. Возвращает число успешно опубликованных."""
        async with self._session_factory() as session:
            repo = OutboxRepository(session)
            messages = await repo.claim_batch(self._batch_size)
            if not messages:
                await session.rollback()
                return 0

            published = 0
            for message in messages:
                try:
                    await self._broker.publish(
                        message.payload,
                        exchange=resolve_exchange(message.exchange),
                        routing_key=message.routing_key,
                        message_id=str(message.id),
                        content_type="application/json",
                        persist=True,
                        headers={HEADER_RETRY_COUNT: 0},
                    )
                except Exception as exc:
                    logger.warning(
                        "Не удалось опубликовать событие %s (попытка %s): %r",
                        message.id,
                        message.attempts + 1,
                        exc,
                    )
                    repo.mark_attempt_failed(
                        message,
                        repr(exc),
                        max_attempts=self._max_attempts,
                        base_delay=self._retry_base_delay,
                    )
                else:
                    repo.mark_published(message)
                    published += 1

            await session.commit()

        if published:
            logger.info("Опубликовано событий из outbox: %s из %s", published, len(messages))
        return published

"""Политика повторных попыток обработки сообщений и отправка в DLQ."""

import logging
from datetime import UTC, datetime

from faststream.rabbit import RabbitBroker
from faststream.rabbit.annotations import RabbitMessage

from app.broker.topology import (
    HEADER_FAILED_AT,
    HEADER_FAILURE_REASON,
    HEADER_RETRY_COUNT,
    ROUTING_DLQ,
    ROUTING_RETRY,
    dlx_exchange,
    payments_exchange,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_retry_count(message: RabbitMessage) -> int:
    """Номер уже сделанных повторов, прочитанный из заголовка сообщения."""
    raw = (message.headers or {}).get(HEADER_RETRY_COUNT, 0)
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return 0


def compute_retry_delay(retry_number: int) -> float:
    """Задержка перед повтором с номером `retry_number` (нумерация с 1).

    При настройках по умолчанию: 5с → 10с → 20с.
    """
    exponent = max(retry_number - 1, 0)
    return settings.retry_base_delay * (settings.retry_multiplier**exponent)


async def schedule_retry(
    broker: RabbitBroker,
    message: RabbitMessage,
    *,
    retry_number: int,
    reason: str,
) -> float:
    """Перекладывает сообщение в очередь отложенных повторов.

    TTL задаётся на самом сообщении (`expiration`), поэтому каждая попытка может иметь
    собственную задержку. По истечении TTL RabbitMQ сам вернёт сообщение в payments.new
    через dead-letter-биндинг очереди payments.retry.
    """
    delay = compute_retry_delay(retry_number)
    headers = dict(message.headers or {})
    headers[HEADER_RETRY_COUNT] = retry_number
    headers[HEADER_FAILURE_REASON] = reason[:500]

    await broker.publish(
        message.body,
        exchange=payments_exchange,
        routing_key=ROUTING_RETRY,
        headers=headers,
        expiration=delay,
        persist=True,
        content_type="application/json",
    )
    logger.warning(
        "Повтор №%s запланирован через %.1f с. Причина: %s", retry_number, delay, reason
    )
    return delay


async def send_to_dlq(
    broker: RabbitBroker,
    message: RabbitMessage,
    *,
    reason: str,
) -> None:
    """Отправляет окончательно упавшее сообщение в DLQ с причиной сбоя в заголовках."""
    headers = dict(message.headers or {})
    headers[HEADER_FAILURE_REASON] = reason[:500]
    headers[HEADER_FAILED_AT] = datetime.now(UTC).isoformat()

    await broker.publish(
        message.body,
        exchange=dlx_exchange,
        routing_key=ROUTING_DLQ,
        headers=headers,
        persist=True,
        content_type="application/json",
    )
    logger.error("Сообщение отправлено в %s. Причина: %s", ROUTING_DLQ, reason)

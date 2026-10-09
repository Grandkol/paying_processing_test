"""Подписчик очереди payments.new — единственный consumer сервиса."""

import logging

from faststream import AckPolicy
from faststream.rabbit.annotations import RabbitMessage

from app.broker.broker import broker
from app.broker.topology import new_queue, payments_exchange
from app.consumer.processor import PaymentProcessor
from app.consumer.retry import get_retry_count, schedule_retry, send_to_dlq
from app.core.config import settings
from app.core.exceptions import WebhookDeliveryError
from app.db.session import session_factory
from app.schemas.events import PaymentCreatedEvent

logger = logging.getLogger(__name__)


@broker.subscriber(
    new_queue,
    payments_exchange,
    ack_policy=AckPolicy.REJECT_ON_ERROR,
)
async def handle_payment_created(event: PaymentCreatedEvent, message: RabbitMessage) -> None:
    """Обрабатывает событие «платёж создан».

    Полный цикл: получить платёж, прогнать через шлюз, записать статус, отправить webhook.
    Ошибки доставки webhook не теряются: сообщение уходит в очередь отложенных повторов,
    а после исчерпания попыток — в DLQ.
    """
    retries_done = get_retry_count(message)
    logger.info(
        "Получено событие %s по платежу %s (сделано повторов: %s)",
        event.event_type,
        event.payment_id,
        retries_done,
    )

    async with session_factory() as session:
        processor = PaymentProcessor(session)
        try:
            await processor.process(event.payment_id)
        except WebhookDeliveryError as exc:
            await _handle_delivery_failure(message, event, retries_done, str(exc))
            return

    logger.info("Платёж %s обработан полностью", event.payment_id)


async def _handle_delivery_failure(
    message: RabbitMessage,
    event: PaymentCreatedEvent,
    retries_done: int,
    reason: str,
) -> None:
    """Решает, что делать с сообщением: отложить повтор или сдать в DLQ."""
    if retries_done >= settings.webhook_max_retries:
        logger.error(
            "Платёж %s: исчерпаны все %s повторных попыток, сообщение уходит в DLQ",
            event.payment_id,
            settings.webhook_max_retries,
        )
        await send_to_dlq(
            broker,
            message,
            reason=f"Исчерпаны {settings.webhook_max_retries} попытки доставки webhook: {reason}",
        )
        return

    await schedule_retry(broker, message, retry_number=retries_done + 1, reason=reason)

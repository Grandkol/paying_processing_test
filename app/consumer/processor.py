"""Обработка платежа: шлюз, статус, webhook."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.consumer.gateway import EmulatedPaymentGateway
from app.consumer.webhook import deliver_webhook
from app.core.exceptions import PaymentNotFoundError
from app.models.enums import PaymentStatus
from app.models.payment import Payment
from app.repositories.payments import PaymentRepository
from app.schemas.events import PaymentWebhookPayload

logger = logging.getLogger(__name__)

WEBHOOK_EVENT = "payment.processed"


class PaymentProcessor:
    """Единственный обработчик платежа: шлюз, запись статуса, отправка webhook.

    Повторная обработка того же платежа безопасна:
      * переход статуса выполняется только из `pending` (условный UPDATE);
      * webhook не отправляется второй раз, если он уже доставлен.
    Поэтому дубль сообщения из брокера (доставка at-least-once) безопасен.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._payments = PaymentRepository(session)
        self._gateway = EmulatedPaymentGateway()

    async def process(self, payment_id: uuid.UUID) -> Payment:
        payment = await self._payments.get(payment_id)
        if payment is None:
            raise PaymentNotFoundError(payment_id)

        if payment.status is PaymentStatus.PENDING:
            payment = await self._authorize(payment)
        else:
            logger.info(
                "Платёж %s уже в статусе %s — обработка пропущена, остаётся только webhook",
                payment.id,
                payment.status.value,
            )

        await self._deliver_webhook(payment)
        return payment

    async def _authorize(self, payment: Payment) -> Payment:
        """Прогоняет платёж через шлюз и фиксирует результат."""
        status = await self._gateway.authorize(payment)

        updated = await self._payments.finalize(payment.id, status)
        await self._session.commit()
        await self._session.refresh(payment)

        if not updated:
            logger.warning(
                "Платёж %s был обработан параллельно, итоговый статус %s",
                payment.id,
                payment.status.value,
            )
        else:
            logger.info("Платёж %s переведён в статус %s", payment.id, payment.status.value)
        return payment

    async def _deliver_webhook(self, payment: Payment) -> None:
        """Отправляет уведомление; при неудаче поднимает WebhookDeliveryError."""
        if not payment.webhook_url:
            logger.info("У платежа %s нет webhook_url — уведомление не требуется", payment.id)
            return

        if payment.webhook_delivered_at is not None:
            logger.info("Webhook по платежу %s уже доставлен ранее", payment.id)
            return

        await self._payments.register_webhook_attempt(payment.id)
        await self._session.commit()

        payload = PaymentWebhookPayload(
            event=WEBHOOK_EVENT,
            payment_id=payment.id,
            status=payment.status.value,
            amount=f"{payment.amount:.2f}",
            currency=payment.currency.value,
            processed_at=payment.processed_at,
        )

        await deliver_webhook(payment.webhook_url, payload)

        await self._payments.mark_webhook_delivered(payment.id)
        await self._session.commit()
        await self._session.refresh(payment)

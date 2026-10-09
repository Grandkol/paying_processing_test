"""Сценарий создания платежа."""

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.broker.topology import EXCHANGE_PAYMENTS, ROUTING_NEW
from app.core.exceptions import IdempotencyConflictError
from app.models.enums import PaymentStatus
from app.models.payment import Payment
from app.repositories.outbox import OutboxRepository
from app.repositories.payments import PaymentRepository
from app.schemas.events import PAYMENT_CREATED, PaymentCreatedEvent
from app.schemas.payment import PaymentCreate

logger = logging.getLogger(__name__)


def build_request_fingerprint(data: PaymentCreate) -> str:
    """Отпечаток тела запроса: отличает повтор от подмены тела при том же ключе."""
    canonical = json.dumps(
        data.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PaymentService:
    """Операции над платежами, доступные через API."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._payments = PaymentRepository(session)
        self._outbox = OutboxRepository(session)

    async def get_payment(self, payment_id: uuid.UUID) -> Payment | None:
        return await self._payments.get(payment_id)

    async def create_payment(self, data: PaymentCreate, idempotency_key: str) -> Payment:
        """Создаёт платёж и событие для брокера в одной транзакции.

        Повторный запрос с тем же Idempotency-Key и тем же телом возвращает уже
        существующий платёж и не публикует второе событие.

        Платёж и запись outbox фиксируются одним COMMIT: не бывает ни платежа без
        события, ни события без платежа. Гонку одновременных запросов разрешает
        уникальный индекс: проигравший INSERT ловит IntegrityError и забирает уже
        созданный платёж.
        """
        fingerprint = build_request_fingerprint(data)

        existing = await self._payments.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return self._ensure_same_request(existing, fingerprint, idempotency_key)

        payment = Payment(
            id=uuid.uuid4(),
            amount=data.amount,
            currency=data.currency,
            description=data.description,
            payment_metadata=data.metadata,
            status=PaymentStatus.PENDING,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            webhook_url=str(data.webhook_url) if data.webhook_url else None,
        )
        self._payments.add(payment)

        event = PaymentCreatedEvent(
            event_id=uuid.uuid4(),
            event_type=PAYMENT_CREATED,
            payment_id=payment.id,
            occurred_at=datetime.now(UTC),
        )
        self._outbox.add(
            message_id=event.event_id,
            aggregate_id=payment.id,
            event_type=event.event_type,
            exchange=EXCHANGE_PAYMENTS,
            routing_key=ROUTING_NEW,
            payload=event.model_dump(mode="json"),
        )

        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            concurrent = await self._payments.get_by_idempotency_key(idempotency_key)
            if concurrent is None:
                raise
            logger.info(
                "Повторный запрос с Idempotency-Key=%s обработан как дубль", idempotency_key
            )
            return self._ensure_same_request(concurrent, fingerprint, idempotency_key)

        logger.info("Создан платёж %s, событие %s положено в outbox", payment.id, event.event_id)
        return payment

    @staticmethod
    def _ensure_same_request(payment: Payment, fingerprint: str, key: str) -> Payment:
        if payment.request_fingerprint != fingerprint:
            raise IdempotencyConflictError(key)
        return payment

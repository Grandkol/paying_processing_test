"""Схемы событий, которые ходят через RabbitMQ."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

PAYMENT_CREATED = "payment.created"


class PaymentCreatedEvent(BaseModel):
    """Событие «платёж создан».

    Содержит только идентификаторы: актуальное состояние платежа consumer читает из БД.
    Поэтому событие не устаревает и его безопасно повторять.
    """

    model_config = ConfigDict(extra="ignore")

    event_id: uuid.UUID
    event_type: str = PAYMENT_CREATED
    payment_id: uuid.UUID
    occurred_at: datetime


class PaymentWebhookPayload(BaseModel):
    """Тело webhook-уведомления, отправляемого клиенту."""

    event: str
    payment_id: uuid.UUID
    status: str
    amount: str
    currency: str
    processed_at: datetime | None

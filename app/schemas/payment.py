"""Pydantic-схемы API платежей."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import AliasChoices, AnyHttpUrl, BaseModel, ConfigDict, Field

from app.models.enums import Currency, PaymentStatus

Amount = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]


class PaymentCreate(BaseModel):
    """Тело запроса на создание платежа."""

    model_config = ConfigDict(extra="forbid")

    amount: Amount = Field(description="Сумма платежа, больше нуля.")
    currency: Currency = Field(description="Валюта платежа.")
    description: str | None = Field(default=None, max_length=512)
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Произвольные дополнительные данные."
    )
    webhook_url: AnyHttpUrl | None = Field(
        default=None, description="URL для уведомления о результате обработки."
    )


class PaymentAccepted(BaseModel):
    """Ответ на создание платежа (202 Accepted)."""

    payment_id: uuid.UUID
    status: PaymentStatus
    created_at: datetime


class PaymentRead(BaseModel):
    """Детальная информация о платеже.

    Поле `metadata` читается из атрибута `payment_metadata` ORM-модели.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount: Decimal
    currency: Currency
    description: str | None
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("payment_metadata", "metadata"),
    )
    status: PaymentStatus
    idempotency_key: str
    webhook_url: str | None
    webhook_attempts: int
    webhook_delivered_at: datetime | None
    created_at: datetime
    processed_at: datetime | None

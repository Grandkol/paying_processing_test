"""Перечисления предметной области."""

from enum import StrEnum


class Currency(StrEnum):
    """Поддерживаемые валюты платежа."""

    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class PaymentStatus(StrEnum):
    """Жизненный цикл платежа: pending -> succeeded | failed."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class OutboxStatus(StrEnum):
    """Состояние записи в outbox."""

    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"

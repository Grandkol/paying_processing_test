"""Исключения предметной области."""


class DomainError(Exception):
    """Базовое исключение сервиса."""


class PaymentNotFoundError(DomainError):
    """Платёж не найден."""

    def __init__(self, payment_id: object) -> None:
        super().__init__(f"Платёж {payment_id} не найден")
        self.payment_id = payment_id


class IdempotencyConflictError(DomainError):
    """Idempotency-Key уже использован, но с другим телом запроса."""

    def __init__(self, key: str) -> None:
        super().__init__(f"Idempotency-Key '{key}' уже использован с другим телом запроса")
        self.key = key


class WebhookDeliveryError(DomainError):
    """Не удалось доставить webhook-уведомление."""

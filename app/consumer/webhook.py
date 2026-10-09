"""Отправка webhook-уведомлений клиенту."""

import logging

import httpx

from app.core.config import settings
from app.core.exceptions import WebhookDeliveryError
from app.schemas.events import PaymentWebhookPayload

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


async def startup_http_client() -> None:
    """Создаёт переиспользуемый HTTP-клиент (один пул соединений на процесс)."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=settings.webhook_timeout)


async def shutdown_http_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def get_http_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("HTTP-клиент не инициализирован: вызовите startup_http_client()")
    return _client


async def deliver_webhook(url: str, payload: PaymentWebhookPayload) -> None:
    """Отправляет POST с результатом обработки платежа.

    Успехом считается любой 2xx. Сетевая ошибка, таймаут, 4xx и 5xx поднимают
    `WebhookDeliveryError`, а он запускает повторные попытки.
    """
    client = get_http_client()
    try:
        response = await client.post(
            url,
            json=payload.model_dump(mode="json"),
            headers={
                "Content-Type": "application/json",
                "X-Event-Type": payload.event,
                "X-Payment-Id": str(payload.payment_id),
            },
        )
    except httpx.HTTPError as exc:
        raise WebhookDeliveryError(f"Webhook {url} недоступен: {exc!r}") from exc

    if not response.is_success:
        raise WebhookDeliveryError(
            f"Webhook {url} ответил {response.status_code}: {response.text[:200]}"
        )

    logger.info("Webhook доставлен на %s, код %s", url, response.status_code)

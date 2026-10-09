"""Эмуляция внешнего платёжного шлюза."""

import asyncio
import logging
import random

from app.core.config import settings
from app.models.enums import PaymentStatus
from app.models.payment import Payment

logger = logging.getLogger(__name__)


class EmulatedPaymentGateway:
    """Шлюз-заглушка: отвечает через 2–5 секунд и в 10% случаев возвращает отказ.

    Отказ шлюза — бизнес-результат, а не сбой обработки: платёж получает статус
    `failed`, повторных попыток не будет.
    """

    async def authorize(self, payment: Payment) -> PaymentStatus:
        delay = random.uniform(settings.gateway_min_delay, settings.gateway_max_delay)
        logger.info("Платёж %s отправлен в шлюз, ожидание %.2f с", payment.id, delay)
        await asyncio.sleep(delay)

        status = (
            PaymentStatus.SUCCEEDED
            if random.random() < settings.gateway_success_rate
            else PaymentStatus.FAILED
        )
        logger.info("Шлюз вернул по платежу %s статус %s", payment.id, status.value)
        return status

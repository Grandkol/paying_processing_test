"""Эндпоинты платежей."""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import IdempotencyKeyDep, SessionDep
from app.core.exceptions import IdempotencyConflictError
from app.schemas.payment import PaymentAccepted, PaymentCreate, PaymentRead
from app.services.payments import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "",
    response_model=PaymentAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Создать платёж",
    responses={
        202: {"description": "Платёж принят в обработку"},
        400: {"description": "Отсутствует Idempotency-Key"},
        401: {"description": "Некорректный API-ключ"},
        409: {"description": "Idempotency-Key уже использован с другим телом запроса"},
        422: {"description": "Ошибка валидации тела запроса"},
    },
)
async def create_payment(
    payload: PaymentCreate,
    idempotency_key: IdempotencyKeyDep,
    session: SessionDep,
) -> PaymentAccepted:
    """Принимает платёж в обработку.

    Платёж сохраняется со статусом `pending`, событие для consumer-а ложится в outbox
    в той же транзакции. Обработка идёт асинхронно.
    """
    service = PaymentService(session)
    try:
        payment = await service.create_payment(payload, idempotency_key)
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return PaymentAccepted(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentRead,
    summary="Получить информацию о платеже",
    responses={
        401: {"description": "Некорректный API-ключ"},
        404: {"description": "Платёж не найден"},
    },
)
async def get_payment(payment_id: uuid.UUID, session: SessionDep) -> PaymentRead:
    """Возвращает детальную информацию о платеже."""
    payment = await PaymentService(session).get_payment(payment_id)
    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Платёж {payment_id} не найден",
        )
    return PaymentRead.model_validate(payment)

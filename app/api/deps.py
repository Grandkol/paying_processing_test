"""Зависимости FastAPI: аутентификация и сессия БД."""

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session

API_KEY_HEADER = "X-API-Key"
IDEMPOTENCY_HEADER = "Idempotency-Key"


async def require_api_key(
    x_api_key: Annotated[
        str | None,
        Header(alias=API_KEY_HEADER, description="Статический API-ключ сервиса."),
    ] = None,
) -> None:
    """Проверяет статический API-ключ.

    Сравнение идёт через `compare_digest`: время ответа не должно зависеть от того,
    сколько символов ключа угадано.
    """
    if x_api_key is None or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный или отсутствующий API-ключ",
            headers={"WWW-Authenticate": API_KEY_HEADER},
        )


async def get_idempotency_key(
    idempotency_key: Annotated[
        str | None,
        Header(alias=IDEMPOTENCY_HEADER, description="Уникальный ключ запроса."),
    ] = None,
) -> str:
    """Достаёт обязательный заголовок Idempotency-Key."""
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Заголовок {IDEMPOTENCY_HEADER} обязателен",
        )
    if len(idempotency_key) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Заголовок {IDEMPOTENCY_HEADER} не длиннее 255 символов",
        )
    return idempotency_key.strip()


SessionDep = Annotated[AsyncSession, Depends(get_session)]
IdempotencyKeyDep = Annotated[str, Depends(get_idempotency_key)]

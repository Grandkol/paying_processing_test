"""ASGI-приложение сервиса (процесс `api`)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Подключение к RabbitMQ здесь не нужно: в брокер публикует outbox-публикатор."""
    setup_logging()
    yield
    await engine.dispose()


app = FastAPI(
    title="Сервис процессинга платежей",
    description=(
        "Асинхронная обработка платежей: API принимает запрос, событие уходит через "
        "transactional outbox в RabbitMQ, consumer обрабатывает платёж и отправляет webhook."
    ),
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(api_router)


@app.get("/health", tags=["service"], summary="Проверка живости")
async def health() -> dict[str, str]:
    """Без аутентификации: эндпоинт опрашивает healthcheck docker."""
    return {"status": "ok", "service": settings.app_name}


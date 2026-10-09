"""Конфигурация сервиса. Все значения читаются из переменных окружения."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "payments-processing"
    log_level: str = "INFO"

    api_key: str = Field(
        default="local-dev-api-key",
        description="Статический ключ, который ожидается в заголовке X-API-Key.",
    )

    database_url: str = "postgresql+asyncpg://payments:payments@postgres:5432/payments"
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 5

    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    consumer_prefetch_count: int = 10

    outbox_poll_interval: float = Field(
        default=1.0, description="Пауза между опросами таблицы outbox, сек."
    )
    outbox_batch_size: int = Field(
        default=50, description="Сколько событий забирать за один проход."
    )
    outbox_max_attempts: int = Field(
        default=10, description="После скольких неудачных публикаций событие помечается failed."
    )
    outbox_retry_base_delay: float = Field(
        default=2.0, description="База экспоненциальной задержки повторной публикации, сек."
    )

    gateway_min_delay: float = 2.0
    gateway_max_delay: float = 5.0
    gateway_success_rate: float = Field(default=0.9, ge=0.0, le=1.0)

    webhook_timeout: float = 5.0
    webhook_max_retries: int = Field(
        default=3,
        description="Количество повторных попыток обработки сообщения до отправки в DLQ.",
    )
    retry_base_delay: float = Field(
        default=5.0, description="База экспоненциальной задержки повторной обработки, сек."
    )
    retry_multiplier: float = 2.0


@lru_cache
def get_settings() -> Settings:
    """Настройки кэшируются: объект создаётся один раз на процесс."""
    return Settings()


settings = get_settings()

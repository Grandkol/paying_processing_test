"""Настройка логирования, одинаковая для всех процессов сервиса."""

import logging
import sys

from app.core.config import settings

_LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"


def setup_logging() -> None:
    """Настраивает корневой логгер на вывод в stdout (чтобы логи забирал docker)."""
    logging.basicConfig(
        level=settings.log_level.upper(),
        format=_LOG_FORMAT,
        stream=sys.stdout,
        force=True,
    )
    logging.getLogger("aio_pika").setLevel(logging.WARNING)
    logging.getLogger("aiormq").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

"""Точка входа процесса `outbox-publisher`.

Запуск: `faststream run app.workers.outbox_publisher:app`
Используется FastStream-приложение, чтобы получить готовое подключение к брокеру
и корректную обработку SIGTERM/SIGINT.
"""

import asyncio

from faststream import FastStream

from app.broker.broker import broker
from app.broker.topology import declare_topology
from app.core.logging import setup_logging
from app.db.session import engine, session_factory
from app.outbox.publisher import OutboxPublisher

setup_logging()

app = FastStream(broker)

_publisher = OutboxPublisher(broker, session_factory)
_task: asyncio.Task[None] | None = None


@app.after_startup
async def on_startup() -> None:
    global _task
    await declare_topology(broker)
    _task = asyncio.create_task(_publisher.run_forever(), name="outbox-publisher")


@app.on_shutdown
async def on_shutdown() -> None:
    _publisher.stop()
    if _task is not None:
        await asyncio.wait_for(_task, timeout=30)
    await engine.dispose()

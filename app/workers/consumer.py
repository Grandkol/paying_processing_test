"""Точка входа процесса `consumer`.

Запуск: `faststream run app.workers.consumer:app`
"""

from faststream import FastStream

from app.broker.broker import broker
from app.broker.topology import declare_topology
from app.consumer import handler as _handler  # noqa: F401
from app.consumer.webhook import shutdown_http_client, startup_http_client
from app.core.logging import setup_logging
from app.db.session import engine

setup_logging()

app = FastStream(broker)


@app.after_startup
async def on_startup() -> None:
    """Очереди объявляем после подключения: операция идемпотентна,
    поэтому порядок запуска контейнеров не важен."""
    await declare_topology(broker)
    await startup_http_client()


@app.on_shutdown
async def on_shutdown() -> None:
    await shutdown_http_client()
    await engine.dispose()

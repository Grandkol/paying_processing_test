"""Единственный экземпляр RabbitBroker на процесс."""

from faststream.rabbit import Channel, RabbitBroker

from app.core.config import settings

broker = RabbitBroker(
    settings.rabbitmq_url,
    default_channel=Channel(
        prefetch_count=settings.consumer_prefetch_count,
        publisher_confirms=True,
    ),
    reconnect_interval=5.0,
    graceful_timeout=30.0,
)

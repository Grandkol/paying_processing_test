"""Топология RabbitMQ: обменники, очереди и правила переливания сообщений.

                     ┌──────────────────────────┐
   outbox publisher  │ exchange: payments       │
   ─── payments.new ─▶  (direct)                │
                     └──┬──────────────────┬────┘
            payments.new│                  │payments.retry
                        ▼                  ▼
                ┌───────────────┐   ┌───────────────────────────┐
                │ payments.new  │   │ payments.retry            │
                │ (consumer)    │   │ per-message TTL, затем    │
                │ DLX ─┐        │   │ DLX ─▶ payments.new       │
                └──────┼────────┘   └───────────────────────────┘
                       │ reject
                       ▼
             ┌──────────────────────┐
             │ exchange payments.dlx│──payments.dlq──▶ payments.dlq
             └──────────────────────┘

Задержка повторной обработки задаётся на каждом сообщении (`expiration`), а не на
очереди: TTL очереди один для всех сообщений и выдержки 5с → 10с → 20с не даст.
"""

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

EXCHANGE_PAYMENTS = "payments"
EXCHANGE_DLX = "payments.dlx"

QUEUE_NEW = "payments.new"
QUEUE_RETRY = "payments.retry"
QUEUE_DLQ = "payments.dlq"

ROUTING_NEW = "payments.new"
ROUTING_RETRY = "payments.retry"
ROUTING_DLQ = "payments.dlq"

HEADER_RETRY_COUNT = "x-retry-count"
HEADER_FAILURE_REASON = "x-failure-reason"
HEADER_FAILED_AT = "x-failed-at"

payments_exchange = RabbitExchange(
    EXCHANGE_PAYMENTS,
    type=ExchangeType.DIRECT,
    durable=True,
)

dlx_exchange = RabbitExchange(
    EXCHANGE_DLX,
    type=ExchangeType.DIRECT,
    durable=True,
)

new_queue = RabbitQueue(
    QUEUE_NEW,
    durable=True,
    routing_key=ROUTING_NEW,
    arguments={
        "x-dead-letter-exchange": EXCHANGE_DLX,
        "x-dead-letter-routing-key": ROUTING_DLQ,
    },
)

retry_queue = RabbitQueue(
    QUEUE_RETRY,
    durable=True,
    routing_key=ROUTING_RETRY,
    arguments={
        "x-dead-letter-exchange": EXCHANGE_PAYMENTS,
        "x-dead-letter-routing-key": ROUTING_NEW,
    },
)

dlq_queue = RabbitQueue(
    QUEUE_DLQ,
    durable=True,
    routing_key=ROUTING_DLQ,
)


async def declare_topology(broker: RabbitBroker) -> None:
    """Объявляет обменники, очереди и связки.

    Вызывается при старте любого процесса, который работает с брокером: объявление
    идемпотентно, поэтому порядок запуска контейнеров не важен.
    """
    payments = await broker.declare_exchange(payments_exchange)
    dlx = await broker.declare_exchange(dlx_exchange)

    declared_new = await broker.declare_queue(new_queue)
    declared_retry = await broker.declare_queue(retry_queue)
    declared_dlq = await broker.declare_queue(dlq_queue)

    await declared_new.bind(payments, routing_key=ROUTING_NEW)
    await declared_retry.bind(payments, routing_key=ROUTING_RETRY)
    await declared_dlq.bind(dlx, routing_key=ROUTING_DLQ)


EXCHANGES: dict[str, RabbitExchange] = {
    EXCHANGE_PAYMENTS: payments_exchange,
    EXCHANGE_DLX: dlx_exchange,
}


def resolve_exchange(name: str) -> RabbitExchange:
    """Возвращает описание обменника по имени."""
    try:
        return EXCHANGES[name]
    except KeyError as exc:
        raise ValueError(f"Неизвестный обменник: {name!r}") from exc

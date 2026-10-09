# Асинхронный сервис процессинга платежей

Сервис принимает запросы на оплату, обрабатывает их асинхронно через эмуляцию
внешнего платёжного шлюза и уведомляет клиента о результате через webhook.

Два эндпоинта: `POST /api/v1/payments` создаёт платёж и отвечает `202`,
`GET /api/v1/payments/{payment_id}` отдаёт его состояние. Оба требуют заголовок
`X-API-Key`, создание — ещё и `Idempotency-Key`.

Внутри четыре процесса: `api` пишет платёж и событие в БД одной транзакцией,
`outbox-publisher` перекладывает события в RabbitMQ, `consumer` проводит платёж
через шлюз и отправляет webhook, `migrator` накатывает миграции. Доставка событий
держится на transactional outbox, повторы webhook идут с экспоненциальной задержкой,
окончательно упавшие сообщения попадают в Dead Letter Queue.

Стек: FastAPI + Pydantic v2, SQLAlchemy 2.0 (async), PostgreSQL 16,
RabbitMQ 3.13 (FastStream), Alembic, Docker Compose.

## Запуск

Нужен Docker с Compose v2 (`docker compose`).

```bash
cp .env.example .env
docker compose up --build
```

| Что | Адрес |
|---|---|
| Swagger UI с примерами запросов | http://localhost:8000/docs |
| RabbitMQ Management | http://localhost:15672 (guest / guest) |

Настройки задаются переменными окружения, полный список со значениями
по умолчанию в `.env.example`.

Остановить и убрать данные:

```bash
docker compose down -v
```

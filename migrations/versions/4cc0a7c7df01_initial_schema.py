"""Начальная схема: таблицы payments и outbox.

Revision ID: 4cc0a7c7df01
Revises: 
Create Date: 2026-10-09 11:57:07.137434+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '4cc0a7c7df01'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('outbox',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('aggregate_id', sa.Uuid(), nullable=False),
    sa.Column('event_type', sa.String(length=128), nullable=False),
    sa.Column('exchange', sa.String(length=255), nullable=False),
    sa.Column('routing_key', sa.String(length=255), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.Enum('pending', 'published', 'failed', name='outbox_status'), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('available_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_outbox_aggregate_id'), 'outbox', ['aggregate_id'], unique=False)
    op.create_index('ix_outbox_dispatch', 'outbox', ['status', 'available_at'], unique=False)
    op.create_table('payments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('currency', sa.Enum('RUB', 'USD', 'EUR', name='currency'), nullable=False),
    sa.Column('description', sa.String(length=512), nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.Enum('pending', 'succeeded', 'failed', name='payment_status'), nullable=False),
    sa.Column('idempotency_key', sa.String(length=255), nullable=False),
    sa.Column('request_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('webhook_url', sa.String(length=2048), nullable=True),
    sa.Column('webhook_attempts', sa.Integer(), nullable=False),
    sa.Column('webhook_delivered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('idempotency_key')
    )
    op.create_index('ix_payments_status_created_at', 'payments', ['status', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_payments_status_created_at', table_name='payments')
    op.drop_table('payments')
    op.drop_index('ix_outbox_dispatch', table_name='outbox')
    op.drop_index(op.f('ix_outbox_aggregate_id'), table_name='outbox')
    op.drop_table('outbox')

    sa.Enum(name='payment_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='currency').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='outbox_status').drop(op.get_bind(), checkfirst=True)

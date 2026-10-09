"""Базовый класс декларативных моделей и общие типы столбцов."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Общий базовый класс для всех моделей."""


def enum_column(enum_cls: type, name: str) -> Enum:
    """Enum, который хранит в БД значения (lowercase), а не имена членов."""
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda cls: [member.value for member in cls],
        native_enum=True,
    )


class TimestampMixin:
    """Время создания записи, выставляется базой."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

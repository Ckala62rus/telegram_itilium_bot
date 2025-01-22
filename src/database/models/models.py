import datetime
from typing import Optional

from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    MetaData, ForeignKey, text
)
from sqlalchemy.orm import Mapped, mapped_column

from database.db import Base


# metadata_obj = MetaData()
#
# workers_table = Table(
#     "workers",
#     metadata_obj,
#     Column("id", Integer, primary_key=True),
#     Column("username", String, primary_key=True),
#     Column("first_name", String, primary_key=True),
# )

# class BaseModel(Base):
#     __abstract__ = True
#
#     id: Mapped[int] = mapped_column(primary_key=True)
#     created_at: Mapped[datetime.datetime] = mapped_column(
#         server_default=text("TIMEZONE('utc', now())")
#     )
#     updated_at: Mapped[datetime.datetime] = mapped_column(
#         server_default=text("TIMEZONE('utc', now())"),
#         onupdate=datetime.datetime.utcnow()
#     )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(nullable=True)
    telegram_id: Mapped[int] = mapped_column(
        nullable=False,
        unique=True
    )
    phone_number: Mapped[Optional[str]]
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_staff: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_ban: Mapped[bool] = mapped_column(default=False, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=text("TIMEZONE('utc', now())")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=text("TIMEZONE('utc', now())"),
        onupdate=datetime.datetime.utcnow()
    )


class Commands(Base):
    __tablename__ = "commands"

    id: Mapped[int] = mapped_column(primary_key=True)
    command: Mapped[str]
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        server_default=text("TIMEZONE('utc', now())")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=text("TIMEZONE('utc', now())"),
        onupdate=datetime.datetime.utcnow()
    )

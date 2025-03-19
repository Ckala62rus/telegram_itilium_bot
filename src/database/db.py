import asyncio
import logging
import sys

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.ext.declarative import declarative_base
from config.configuration import settings

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# print(settings.SQLALCHEMY_DATABASE_URL)
async_engine = create_async_engine(
    url=settings.SQLALCHEMY_DATABASE_URL,
    # url="postgresql+psycopg://postgres:postgres@db_telegram_bot:5432/alch",
    # url="postgresql+psycopg://pguser:000000@localhost:5432/mydb",
    echo=True,
    # pool_size=5,
    # max_overflow=10
)

session_factory = async_sessionmaker(async_engine)
Base = declarative_base()

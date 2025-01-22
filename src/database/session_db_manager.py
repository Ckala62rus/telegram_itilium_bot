from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from config.configuration import settings

engine = create_async_engine(
    url=settings.SQLALCHEMY_DATABASE_URL,
    echo=True,
)

async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False)


class SessionContextManager:

    def __init__(self) -> None:
        self.session_factory = async_session_maker
        self.session = None

    async def __aenter__(self) -> None:
        self.session = self.session_factory()

    async def __aexit__(self, *args: object) -> None:
        await self.rollback()

    async def commit(self) -> None:
        await self.session.commit()
        await self.session.close()
        self.session = None

    async def rollback(self) -> None:
        await self.session.rollback()
        await self.session.close()
        self.session = None


db_session = SessionContextManager()

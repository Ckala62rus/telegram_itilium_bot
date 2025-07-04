from sqlalchemy.ext.asyncio import AsyncSession
import logging

from database.models.models import Commands

logger = logging.getLogger(__name__)


async def add_user_command(session: AsyncSession, data: dict):
    user = Commands(
        command=data["command"],
        user_id=data["user_id"],
    )
    session.add(user)

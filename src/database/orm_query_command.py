from sqlalchemy.ext.asyncio import AsyncSession

from database.models.models import Commands


async def add_user_command(session: AsyncSession, data: dict):
    user = Commands(
        command=data["command"],
        user_id=data["user_id"],
    )
    session.add(user)

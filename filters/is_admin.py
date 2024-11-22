from aiogram.filters import BaseFilter
from aiogram.types import Message

from create_bot import env_admins
from db.r_operations import redis_check_admin


# class IsAdmin(BaseFilter):
#     def __init__(self) -> None:
#         pass
#
#     async def __call__(self, message: Message) -> bool:
#         return await redis_check_admin(message.from_user.id)


class IsAdmin(BaseFilter):
    def __init__(self) -> None:
        pass

    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in env_admins

from aiogram.filters import BaseFilter
from aiogram.types import Message

from create_bot import env_admins


class IsAdmin(BaseFilter):
    def __init__(self) -> None:
        pass

    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in env_admins

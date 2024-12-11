from aiogram.types import Message
from aiogram.exceptions import TelegramForbiddenError
from create_bot import bot, env_admins
from db.pg_orm_query import orm_delete_channel_and_association
from sqlalchemy.ext.asyncio import AsyncSession


async def get_bot_link_to_start() -> str:
    bot_info = await bot.get_me()
    return f"https://t.me/{bot_info.username}?start="


async def msg_to_cbk(message: Message):
    raw_buttons = message.text.split("\n")
    clean_buttons = {}
    for btn in raw_buttons:
        text, link = btn.split(":", maxsplit=1)
        clean_buttons[text.strip()] = link.strip()
    return clean_buttons


async def is_subscribed(channels: list, user_id: int) -> bool:
    for channel in channels:
        channel_id = channel.channel_id if hasattr(channel, 'channel_id') else channel
        chat_member = await bot.get_chat_member(channel_id, user_id)
        if chat_member.status in ["restricted", "left", "kicked"]:
            return False
    return True


async def channel_info(session: AsyncSession, channel_id: int):
    try:
        chat = await bot.get_chat(channel_id)
        return chat
    except TelegramForbiddenError:
        await orm_delete_channel_and_association(session=session, channel_id=channel_id)


async def convert_id(old_id: int) -> str:
    old_id_str = str(old_id)
    if old_id_str.startswith("-100"):
        return old_id_str[4:]
    elif old_id_str.startswith("-"):
        return old_id_str[1:]
    return old_id_str


async def get_channel_hyperlink(session: AsyncSession, channel_id: int) -> str:
    chat = await channel_info(session=session, channel_id=channel_id)
    return f"<a href='{chat.invite_link}'>{chat.title}</a>"


async def is_admin(user_id: int) -> bool:
    is_env_admin = user_id in env_admins
    return is_env_admin

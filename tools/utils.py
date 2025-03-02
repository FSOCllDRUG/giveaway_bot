import asyncio
import re

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message

from create_bot import bot, env_admins
from db.pg_engine import session_maker
from db.pg_models import GiveawayStatus
from db.pg_orm_query import orm_get_giveaways_by_sponsor_channel_id, orm_update_giveaway_status, orm_delete_channel, \
    orm_get_user_id_by_giveaway_id, orm_delete_sponsor, orm_get_sponsors_count
from db.r_operations import redis_get_participants_count
from tools.logs_channel import send_log

session = session_maker()


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
        try:
            if chat_member.status in ["restricted", "left", "kicked"]:
                return False
        except TelegramBadRequest as e:
            if "member list is inaccessible" in str(e):
                await send_log(f"Недостаточно прав для проверки подписки в канале "
                               f"{await get_channel_hyperlink(channel_id)}\n\n"
                               f"{e}")
                return False
    return True


async def is_bot_admin(chat_id: int) -> bool:
    try:
        chat = await bot.get_chat(chat_id)
        return chat.invite_link is not None
    except TelegramBadRequest as e:
        await send_log(f"Error checking admin status(utils.py:48): {e}")
        return False


async def convert_id(old_id: int) -> str:
    old_id_str = str(old_id)
    if old_id_str.startswith("-100"):
        return old_id_str[4:]
    elif old_id_str.startswith("-"):
        return old_id_str[1:]
    return old_id_str


async def get_channel_hyperlink(channel_id: int) -> str:
    chat = await channel_info(channel_id=channel_id)
    if chat is None:
        return ""
    else:
        return f"<a href='{chat.invite_link}'>{chat.title}</a>"


async def is_admin(user_id: int) -> bool:
    is_env_admin = user_id in env_admins
    return is_env_admin


async def channel_info(channel_id: int):
    try:
        await asyncio.sleep(1/20)
        chat = await bot.get_chat(channel_id)
        if chat.invite_link is not None:
            return chat
        else:
            return None
    except TelegramForbiddenError:
        return None
    except TelegramBadRequest as e:
        await send_log(f"Error checking channel info(utils.py:79): {e}")
        return None


async def not_admin(chat_id: int, user_id: int = None):
    text = (f"{await get_user_creds(user_id)} удалил меня из канала/группы {chat_id}!\n"
            f"Канал удалён из базы данных.\n"
            f"Идёт обработка связанных с каналом розыгрышей...")
    try:
        await send_log(text)
        await bot.send_message(chat_id=user_id,
                               text=text)
    except Exception as e:
        # await send_log(f"Error in utils.py:93: {e}")
        pass
    try:
        giveaways_ids = await orm_get_giveaways_by_sponsor_channel_id(session, chat_id)
        for giveaway in giveaways_ids:
            if await orm_get_sponsors_count(session, giveaway) > 1:
                await orm_delete_sponsor(session, giveaway, chat_id)
                await send_log(text=f"Спонсор {chat_id} был удалён из розыгрыша #{giveaway}")
            else:
                participants_count = await redis_get_participants_count(giveaway.id)
                await orm_update_giveaway_status(session, giveaway, GiveawayStatus.FINISHED,
                                                 participants_count=participants_count)
                await send_log(text=f"Розыгрыш #{giveaway} завершён принудительно, так как удалён последний спонсор.")
        await orm_delete_channel(session, chat_id)
    except Exception as e:
        # await send_log(f"Error in utils.py:93: {e}")
        pass


async def post_deleted(giveaway_id: int):
    try:
        user_id = await orm_get_user_id_by_giveaway_id(session, giveaway_id)
        await bot.send_message(chat_id=user_id, text=f"Ты удалил пост розыгрыша #{giveaway_id}!\n"
                                                     f"Розыгрыш завершён принудительно "
                                                     f"без определения победителей.\n"
                                                     f"/mygive{giveaway_id}")
        await orm_update_giveaway_status(session, giveaway_id, GiveawayStatus.FINISHED)
    except Exception as e:
        await send_log(f"ОШИБКА ПРИ УДАЛЕНИИ РОЗЫГРЫША:\n/usergive{giveaway_id}\n\n{e}")


async def remove_premium_emoji_tags(text: str) -> str:
    pattern = r'<tg-emoji emoji-id="\d+">([^<]+)</tg-emoji>'
    cleaned_text = re.sub(pattern, r'\1', text)
    return cleaned_text


async def get_user_creds(user_id: int) -> str:
    try:
        user = await bot.get_chat(user_id)
        user_name = user.first_name if user.first_name else "No name"
        user_username = f"@{user.username}" if user.username else f"{user.id}"
        text = f"<a href='tg://user?id={user.id}'>{user_name}</a> ({user_username})"
    except Exception:
        text = f"<a href='tg://user?id={user_id}'>{user_id}</a>"
    return text

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from create_bot import bot, env_admins
from db.pg_engine import session_maker
from db.pg_orm_query import orm_delete_channel, orm_delete_giveaway_with_channel, orm_get_admins_in_channel, \
    orm_get_admin_in_channel

session = session_maker()


# from db.pg_engine import session_maker
#
# session = session_maker()


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


async def is_bot_admin(chat_id: int) -> bool:
    try:
        chat = await bot.get_chat(chat_id)
        return chat.invite_link is not None
    except TelegramBadRequest as e:
        print(f"Error checking admin status: {e}")
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


# "Так как бота убрали из списка администраторов, Ваш канал и связанные с ним розыгрыши были удалены"
async def del_channel_and_giveaways(channel_id: int):
    try:
        await orm_delete_channel(session, channel_id)
    except Exception as e:
        print(f"Error deleting channel: {e}")
    try:
        await orm_delete_giveaway_with_channel(session, channel_id)
    except Exception as e:
        print(f"Error deleting giveaways: {e}")


async def channel_info(channel_id: int):
    try:
        chat = await bot.get_chat(channel_id)
        if chat.invite_link is not None:
            return chat
        else:
            print(f"###\nBot is not admin in channel {channel_id}\n###")
            admin = await orm_get_admin_in_channel(session, channel_id)
            print(admin)
            print(type(admin))
            try:
                await bot.send_message(chat_id=admin,
                                   text="Так как бота убрали из списка администраторов, Ваш канал и связанные с ним "
                                        "розыгрыши были удалены")
            except Exception as e:
                print(f"Error sending message to admin: {e}")
            print(f"Message sent to {admin}")
            await del_channel_and_giveaways(channel_id)
            print(f"###\nDeleted channel {channel_id}\n###")
    except TelegramBadRequest as e:
        print(f"Error checking channel info: {e}")
        return None

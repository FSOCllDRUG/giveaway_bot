from aiogram import Router
from aiogram.types import ChatMemberUpdated

from db.r_operations import redis_temp_channel
from filters.chat_type import ChatType
from tools.utils import not_admin

channel_router = Router()
channel_router.my_chat_member.filter(ChatType("channel"))


@channel_router.my_chat_member()
async def on_chat_member_updated(update: ChatMemberUpdated):
    if update.new_chat_member.status == 'administrator':
        chat_id = update.chat.id
        user_id = update.from_user.id
        await redis_temp_channel(user_id, chat_id)
        print(f"Bot promoted to admin in channel {chat_id} by user {user_id}")
    if update.new_chat_member.status == 'left':
        chat_id = update.chat.id
        user_id = update.from_user.id
        print(f"Bot kicked from channel {chat_id} by user {user_id}")
        await not_admin(chat_id, user_id)

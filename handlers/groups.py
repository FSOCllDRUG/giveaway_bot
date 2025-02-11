from aiogram import Router
from aiogram.types import ChatMemberUpdated

from db.r_operations import redis_temp_channel
from filters.chat_type import ChatType
from tools.logs_channel import send_log
from tools.utils import not_admin, get_user_creds, get_channel_hyperlink

group_router = Router()

group_router.my_chat_member.filter(ChatType(["supergroup", "group"]))


@group_router.my_chat_member()
async def on_chat_member_updated(update: ChatMemberUpdated):
    print(update.new_chat_member.status)
    if update.new_chat_member.status == 'administrator':
        chat_id = update.chat.id
        user_id = update.from_user.id
        await redis_temp_channel(user_id, chat_id)
        print(f"Bot promoted to admin in group/supergroup {chat_id} by user {user_id}")
        await send_log(f"Бот стал админом в группе {await get_channel_hyperlink(chat_id)}\n"
                       f"Пользователь {await get_user_creds(user_id)}"
                       f"\n\n#права")
    # if update.new_chat_member.status == 'member':
    #     chat_id = update.chat.id
    #     user_id = update.from_user.id
    #     print(f"Bot demoted in group/supergroup {chat_id} by user {user_id}")
    #     await not_admin(chat_id, user_id)
    if update.new_chat_member.status == 'left':
        chat_id = update.chat.id
        user_id = update.from_user.id
        print(f"Bot kicked from group/supergroup {chat_id} by user {user_id}")
        await send_log(f"Бот кикнут из группы {chat_id}\n"
                       f"Пользователь {await get_user_creds(user_id)}"
                       f"\n\n#права")
        await not_admin(chat_id, user_id)


from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from create_bot import bot
from db.pg_orm_query import orm_get_admins_id, orm_get_admins
from db.r_operations import redis_upd_admins


async def admins_list_text(session: AsyncSession):
    text = ""
    text += "\n\nСписок добавленных администраторов:\n💼\n"
    added_admins = await orm_get_admins(session)
    i = 1
    for admin in added_admins:
        user_link = f"<a href='tg://user?id={admin.user_id}'>{admin.user_id}</a>"
        text += (
            f"{i}.👤 Телеграм ID: {user_link}\n"
            f"📝 Полное имя: {admin.name}\n"
        )

        if admin.username is not None:
            text += f"🔑 Логин: @{admin.username}\n"
        i += 1
    return text


async def union_admins(lst1, lst2):
    final_list = list(set(lst1) | set(lst2))
    return final_list


async def update_admins(session: AsyncSession, old_admins: list):
    db_admins = await orm_get_admins_id(session)
    admins = await union_admins(old_admins, db_admins)
    await redis_upd_admins(admins)
    return admins


async def get_chat_id(message: Message):
    if message.forward_from_chat:
        return message.forward_from_chat.id
    elif message.forward_from:
        return message.forward_from.id
    elif message.text and message.text.startswith("@"):
        username = message.text
        chat = await bot.get_chat(username)
        return chat.id
    elif message.text and message.text.startswith("https://t.me/"):
        username = message.text.replace("https://t.me/", "@")
        chat = await bot.get_chat(username)
        return chat.id
    else:
        return None


cbk_msg = ("Отправь содержание кнопок вида:\n"
           "текст кнопки:ссылка\n"
           "текст кнопки:ссылка\n\n"
           "Пример: \n<pre>Перейти на сайт:https://example.com\n"
           "Перейти к посту:https://t.me/for_test_ch/3</pre>"
           "\n\n"
           "Количество кнопок должно быть не более 10\n"
           "Кнопки присылать <b><u>ОДНИМ</u></b> сообщением, каждая кнопка с новой строки!")


async def msg_to_cbk(message: Message):
    raw_buttons = message.text.split("\n")
    clean_buttons = {}
    for btn in raw_buttons:
        text, link = btn.split(":", maxsplit=1)
        clean_buttons[text.strip()] = link.strip()
    return clean_buttons


link_to_dev = "https://t.me/xtc_hydra?text=%D0%9F%D1%80%D0%B8%D0%B2%D0%B5%D1%82%2C%20%D1%80%D0%B0%D0%B7%D1%80%D0%B0%D0%B1.%0A%D0%9A%D0%B0%D0%B6%D0%B5%D1%82%D1%81%D1%8F%2C%20%D1%82%D0%B2%D0%BE%D0%B9%20%D0%BF%D1%80%D0%BE%D0%B4%D1%83%D0%BA%D1%82%20%D1%80%D0%B5%D1%88%D0%B8%D0%BB%20%D0%B2%D0%B7%D1%8F%D1%82%D1%8C%20%D0%B2%D1%8B%D1%85%D0%BE%D0%B4%D0%BD%D0%BE%D0%B9%20%D0%B8%20%D0%BD%D0%B5%D0%BC%D0%BD%D0%BE%D0%B3%D0%BE%20%D0%BE%D1%82%D0%B4%D0%BE%D1%85%D0%BD%D1%83%D1%82%D1%8C.%0A%D0%AF%20%D1%82%D1%83%D1%82%20%D0%BE%D0%B1%D0%BD%D0%B0%D1%80%D1%83%D0%B6%D0%B8%D0%BB%D0%B8%20%D0%BD%D0%B5%D0%B1%D0%BE%D0%BB%D1%8C%D1%88%D1%83%D1%8E%20%D0%BF%D1%80%D0%BE%D0%B1%D0%BB%D0%B5%D0%BC%D1%83%2C%20%D0%B8%2C%20%D0%BF%D0%BE%D1%85%D0%BE%D0%B6%D0%B5%2C%20%D0%BE%D0%BD%D0%B0%20%D1%82%D1%80%D0%B5%D0%B1%D1%83%D0%B5%D1%82%20%D1%82%D0%B2%D0%BE%D0%B5%D0%B3%D0%BE%20%D0%BC%D0%B0%D0%B3%D0%B8%D1%87%D0%B5%D1%81%D0%BA%D0%BE%D0%B3%D0%BE%20%D0%BF%D1%80%D0%B8%D0%BA%D0%BE%D1%81%D0%BD%D0%BE%D0%B2%D0%B5%D0%BD%D0%B8%D1%8F.%F0%9F%AA%84%0A%D0%9F%D1%80%D0%BE%D0%B1%D0%BB%D0%B5%D0%BC%D0%B0%3A%20"


sub_channel_id: int = -1002215648888


async def is_subscriber_to_channel(user_id: int) -> bool:
    chat_member = await bot.get_chat_member(sub_channel_id, user_id)
    return chat_member.status not in ["left", "kicked"]

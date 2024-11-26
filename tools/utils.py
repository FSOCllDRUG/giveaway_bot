import datetime

import pytz
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from create_bot import bot
from db.pg_orm_query import orm_get_admins_id, orm_get_admins, orm_get_required_channels
from db.r_operations import redis_upd_admins
from keyboards.inline import get_callback_btns


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


async def is_subscriber_to_channel(session: AsyncSession, user_id: int) -> bool:
    required_channels = await orm_get_required_channels(session)
    allowed = True
    for channel in required_channels:
        chat_member = await bot.get_chat_member(channel.channel_id, user_id)
        if chat_member.status not in ["left", "kicked"]:
            allowed = True
        else:
            allowed = False
    return allowed


# async def channel_info(id: int) -> dict:
async def channel_info(channel_id: int):
    chat = await bot.get_chat(channel_id)
    return chat


async def get_channel_hyperlink(channel_id: int) -> str:
    chat = await channel_info(channel_id)
    return f"<a href='{chat.invite_link}'>{chat.title}</a>"


async def convert_id(old_id: int) -> str:
    old_id_str = str(old_id)
    if old_id_str.startswith("-100"):
        return old_id_str[4:]
    elif old_id_str.startswith("-"):
        return old_id_str[1:]
    return old_id_str


async def datetime_example():
    now = datetime.datetime.now(pytz.timezone('Europe/Moscow'))
    text = ("Примеры:\n"
            f"<code>{(now + datetime.timedelta(minutes=10)).strftime('%d.%m.%Y %H:%M')}</code> - через 10 минут\n"
            f"<code>{(now + datetime.timedelta(hours=1)).strftime('%d.%m.%Y %H:%M')}</code> - через час\n"
            f"<code>{(now + datetime.timedelta(days=1)).strftime('%d.%m.%Y %H:%M')}</code> - через день\n"
            f"<code>{(now + datetime.timedelta(days=7)).strftime('%d.%m.%Y %H:%M')}</code> - через неделю")
    return text


# data = {
#     "message": 2262,
#     "media_type": "photo",
#     "media": "AgACAgIAAxkBAAIIuGdD2TLjf0w-V0AIli_93mkpsitbAAII6jEbhwYgSkyZUVcuuTkFAQADAgADeAADNgQ",
#     "text": "Giveaway text",
#     "button": "Хочу учавствовать",
#     "sponsor_channels": [
#         -1002483088330
#     ],
#     "winners_count": 3,
#     "channel_id": -1002066571816,
#     "post_datetime": "2024-11-25T06:00:00+03:00",
#     "end_count": null,
#     "end_datetime": "2024-11-25T06:01:00+03:00"
# }


async def get_giveaway_preview(data: dict, user_id: int = None, bot=None):
    print(data)
    text = data["text"]
    text += "\n\n<b>Условия участия:</b>\n\n"
    if "extra_conditions" in data:
        text += f'{data["extra_conditions"]}\n\n'
    if "sponsor_channels" not in data or data["channel_id"] not in data["sponsor_channels"]:
        channel = await channel_info(data["channel_id"])
        text += f"✅ Подпишись на <a href='{channel.invite_link}'>{channel.title}</a>\n"
    if "sponsor_channels" in data:
        for channel in data["sponsor_channels"]:
            channel = await channel_info(channel)
            text += f"✅ Подпишись на <a href='{channel.invite_link}'>{channel.title}</a>\n"
    # text += "\nНажми на прикрепленную к посту кнопку👇🏻\n\n\n"
    if "end_datetime" in data:
        text += (f"\nРезультаты розыгрыша: <b"
                 f">{datetime.datetime.fromisoformat(data['end_datetime']).strftime('%d.%m.%Y %H:%M')}</b>\n\n")
    else:
        text += f"\nРезультаты розыгрыша будут при достижении <b>{data['end_count']} участника(ов)</b>\n\n"
    if "media_type" in data:
        if data["media_type"] == "photo":
            await bot.send_photo(chat_id=user_id, photo=data["media"], caption=text,
                                 reply_markup=await get_callback_btns(btns={f"{data['button']}": "empty"}))
        elif data["media_type"] == "video":
            await bot.send_video(chat_id=user_id, video=data["media"], caption=text,
                                 reply_markup=await get_callback_btns(btns={f"{data['button']}": "empty"}))
        elif data["media_type"] == "animation":
            await bot.send_animation(chat_id=user_id, animation=data["media"], caption=text,
                                     reply_markup=await get_callback_btns(btns={f"{data['button']}": "empty"}))
    else:
        await bot.send_message(chat_id=user_id, text=text,
                               reply_markup=await get_callback_btns(btns={f"{data['button']}": "empty"}))


async def get_giveaway_info_text(data: dict) -> str:
    text = "❗️🧾Внимательно перепроверьте розыгрыш🧾❗️\n\n"
    text += f"Пост розыгрыша в {await get_channel_hyperlink(data['channel_id'])}\n\n"
    text += f"🏆 Количество победителей: {data['winners_count']}\n\n"
    text += f"🕒 Время публикации: "
    if "post_datetime" in data:
        text += f"<b>{datetime.datetime.fromisoformat(data['post_datetime']).strftime('%d.%m.%Y %H:%M')}</b>\n"
    else:
        text += "<b>Сразу после сохранения</b>\n\n"
    if "end_datetime" in data:
        text += f"🕒🔚 Результаты розыгрыша в: <b>{datetime.datetime.fromisoformat(data['end_datetime']).strftime('%d.%m.%Y %H:%M')}</b>"
    else:
        text += f"👥🔚 Результаты розыгрыша когда будет достигнуто <b>{data['end_count']} участника(ов)</b>"
    return text


captcha_on_text = ("ℹ️ <i>Вы включили капчу</i>✅\n"
                   "Теперь каждый пользователь перед участием должен будет решить графическую капчу."
                   "При нажатии на кнопу участия пользователь будет перебрасываться в нашего бота, "
                   "где ему будет предложено ввести цифры с картинки. "
                   "После ввода правильных цифр пользователь станет участником конкурса."
                   "Эта функция создана для того, чтобы в конкурсе невозможно было накрутить ботов.")

captcha_off_text = ("ℹ️ <i>Вы отключили капчу</i>❌\n"
                    "Теперь для участия в конкурсе участникам не нужно решать графическую капчу.")

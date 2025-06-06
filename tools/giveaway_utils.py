import asyncio
import datetime
from typing import Any

import aiogram.exceptions
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from create_bot import bot
from db.pg_models import GiveawayStatus
from db.pg_orm_query import orm_get_giveaway_by_id, orm_delete_giveaway, orm_get_user_id_by_giveaway_id
from db.r_operations import redis_get_participants_count, redis_add_participant
from keyboards.inline import get_callback_btns
from tools.texts import encode_giveaway_id, channel_conditions_text
from tools.utils import channel_info, get_bot_link_to_start, convert_id, get_channel_hyperlink, post_deleted, \
    send_log, get_user_creds, session


async def get_giveaway_info_text(data: dict) -> str:
    text = "❗️ <b>Внимательно перепроверьте розыгрыш.</b>\n\n"
    text += f"Пост розыгрыша в {await get_channel_hyperlink(data['channel_id'])}\n\n"
    text += f"🏆<b> Количество победителей: {data['winners_count']}</b>\n\n"
    text += f"🕒 Время публикации: "
    if "post_datetime" in data:
        text += f"<b>{datetime.datetime.fromisoformat(data['post_datetime']).strftime('%d.%m.%Y %H:%M')}</b>\n\n"
    if "end_datetime" in data:
        text += (f"🕒🔚 Результаты розыгрыша в: "
                 f"<b>{datetime.datetime.fromisoformat(data['end_datetime']).strftime('%d.%m.%Y %H:%M')}</b>")
    else:
        text += f"👥🔚 Результаты розыгрыша когда будет достигнуто <b>{data['end_count']} участника(ов)</b>"
    return text


async def get_giveaway_preview(data: dict, user_id: int = None, bot=None):
    text = data["text"]
    text += "\n\n<b>Условия участия:</b>\n\n"
    if "sponsor_channels" not in data or data["channel_id"] not in data["sponsor_channels"]:
        channel = await channel_info(channel_id=data["channel_id"])
        text += await channel_conditions_text(channel)
    if "sponsor_channels" in data:
        for channel in data["sponsor_channels"]:
            channel = await channel_info(channel_id=channel)
            text += await channel_conditions_text(channel)
    if "extra_conditions" in data:
        text += f'{data["extra_conditions"]}\n\n'
    if "end_datetime" in data:
        text += (f"\nРезультаты розыгрыша: <b"
                 f">{datetime.datetime.fromisoformat(data['end_datetime']).strftime('%d.%m.%Y %H:%M')}</b>\n\n")
    else:
        text += f"\nРезультаты розыгрыша будут при достижении <b>{data['end_count']} участника(ов)</b>\n\n"
    try:
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
        return True
    except aiogram.exceptions.TelegramBadRequest as e:
        if "is too long" in str(e):
            await bot.send_message(chat_id=user_id, text="❌Ошибка. Текст слишком длинный!")
            await send_log(text=f"Ошибка при создании розыгрыша у пользователя {await get_user_creds(user_id)}: "
                                f"{e}\n\n❌Ошибка. Текст слишком длинный!")
            return False


async def join_giveaway_link(giveaway_id: int) -> str:
    link = await get_bot_link_to_start()
    encoded = await encode_giveaway_id(giveaway_id)
    link += f"join_giveaway_{encoded}"
    return link


async def not_posted_giveaway(giveaway_id, error_text):
    text = (f"Розыгрыш №{giveaway_id} не опубликован!\n"
            f"Причина: {error_text}\n\n"
            f"Розыгрыш был удалён из базы данных!")
    user_id = await orm_get_user_id_by_giveaway_id(session=session, giveaway_id=giveaway_id)
    await orm_delete_giveaway(session=session, giveaway_id=giveaway_id)
    try:
        await bot.send_message(chat_id=user_id, text=text)
    except TelegramForbiddenError:
        pass
    await send_log(text=text + f"\n\n{await get_user_creds(user_id)}")


async def post_giveaway(giveaway):
    try:
        text = giveaway.text
        buttons = {f"{giveaway.button}": f"{await join_giveaway_link(giveaway.id)}"}
        text += "\n\n<b>Условия участия:</b>\n\n"
        message = None

        if not giveaway.sponsor_channel_ids or giveaway.channel_id not in giveaway.sponsor_channel_ids:
            channel = await channel_info(channel_id=giveaway.channel_id)
            text += await channel_conditions_text(channel)

        if giveaway.sponsor_channel_ids:
            for channel_id in giveaway.sponsor_channel_ids:
                channel = await channel_info(channel_id=channel_id)
                text += await channel_conditions_text(channel)

        if giveaway.extra_conditions:
            text += f"\n{giveaway.extra_conditions}\n\n"

        if giveaway.end_datetime:
            text += (f"\nРезультаты розыгрыша: "
                     f"<b>{giveaway.end_datetime.strftime('%d.%m.%Y %H:%M')}</b>\n\n")
        else:
            text += f"\nРезультаты розыгрыша будут при достижении <b>{giveaway.end_count} участника(ов)</b>\n\n"

        if giveaway.media_type:
            if giveaway.media_type == "photo":
                message = await bot.send_photo(chat_id=giveaway.channel_id, photo=giveaway.media, caption=text,
                                               reply_markup=await get_callback_btns(btns=buttons))
            elif giveaway.media_type == "video":
                message = await bot.send_video(chat_id=giveaway.channel_id, video=giveaway.media, caption=text,
                                               reply_markup=await get_callback_btns(btns=buttons))
            elif giveaway.media_type == "animation":
                message = await bot.send_animation(chat_id=giveaway.channel_id, animation=giveaway.media, caption=text,
                                                   reply_markup=await get_callback_btns(btns=buttons))
        else:
            message = await bot.send_message(chat_id=giveaway.channel_id, text=text,
                                             reply_markup=await get_callback_btns(btns=buttons))
        return message
    except Exception as e:
        await not_posted_giveaway(giveaway_id=giveaway.id, error_text=f"{e}")


async def giveaway_post_notification(giveaway, post_url):
    text = (
        f"Розыгрыш #{giveaway.id} опубликован!\n"
        f"<a href='{post_url}'>Ссылка на розыгрыш</a>\n"
    )
    await bot.send_message(chat_id=giveaway.user_id, text=text)


async def winners_notification(winners: list, message, link=None, check_results=None):
    try:
        chat_id = message.chat.id
        clear_chat_id = await convert_id(chat_id)
        message_id = message.message_id
        post_url = f"https://t.me/c/{clear_chat_id}/{message_id}"
        winners_list = ""
        for i, winner_id in enumerate(winners, start=1):
            winners_list += f"{i}. {await get_user_creds(winner_id)}\n"

        max_length = 4096
        text = (f"🎉<b>Поздравляем!</b>\n\n"
                f"Вы стали победителем <a href='{post_url}'>розыгрыша</a>!🎁\n\n"
                f"<b>Благодарим за участие!</b>\n\n"
                f"Список победителей:\n")

        if len(winners) < 100:
            text += f"{winners_list}\n{link}"
        else:
            text += f"{winners_list}\n"

        text_parts = [text[i:i+max_length] for i in range(0, len(text), max_length)]

        for winner in winners:
            await asyncio.sleep(1 / 20)
            for part in text_parts:
                if len(winners) < 100:
                    await bot.send_message(chat_id=winner, text=part)
                else:
                    await bot.send_message(chat_id=winner, text=part, reply_markup=check_results)
    except aiogram.exceptions.TelegramForbiddenError:
        # Можно добавить изменение статуса рассылки для юзера который заблокировал
        pass


async def giveaway_result_notification(message, giveaway):
    chat_id = message.chat.id
    clear_chat_id = await convert_id(chat_id)
    message_id = message.message_id
    post_url = f"https://t.me/c/{clear_chat_id}/{message_id}"
    text = (
        f"Розыгрыш #{giveaway.id} завершён!\n"
        f"<a href='{post_url}'>Ссылка на результаты</a>\n"
    )
    await bot.send_message(chat_id=giveaway.user_id, text=text)


async def update_button_text(session: AsyncSession, giveaway_id: int) -> InlineKeyboardMarkup | None:
    giveaway = await orm_get_giveaway_by_id(session=session, giveaway_id=giveaway_id)
    if not giveaway:
        return None
    participants_count = await redis_get_participants_count(giveaway_id)
    button_text = f"{giveaway.button} ({participants_count})"
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=button_text, url=f"{await join_giveaway_link(giveaway.id)}")]
    ])
    return buttons


async def update_giveaway_message(session: AsyncSession, giveaway_id: int, chat_id: int, message_id: int):
    new_buttons = await update_button_text(session, giveaway_id)
    channel = await channel_info(chat_id)
    if new_buttons:
        try:
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=new_buttons)
            await asyncio.sleep(1 / 20)
        except TelegramBadRequest as e:
            if "exactly the same" in str(e):
                pass
            elif "message to edit not found" or "MESSAGE_ID_INVALID" in str(e):
                await post_deleted(giveaway_id=giveaway_id)
            else:
                await send_log(text=f"Error while updating button for giveaway:\n/usergive{giveaway_id}"
                                    f"\n{channel.title} {channel.invite_link}\n\n{e}")
        except TelegramForbiddenError as e:
            await send_log(text=f"Error while updating button for giveaway:\n/usergive{giveaway_id}"
                                f"\n{channel.title if channel else chat_id} "
                                f"{channel.invite_link if channel else ''}\n\n"
                                f"{e}")


async def add_participant_to_redis(giveaway_id: int, user_id: int):
    await redis_add_participant(giveaway_id, user_id)


# Можно ускорить(по запросу)
async def check_giveaway_text(session: AsyncSession, giveaway_id: int) -> str | list[str | Any]:
    # Получаем данные о розыгрыше
    giveaway = await orm_get_giveaway_by_id(session=session, giveaway_id=giveaway_id)
    if giveaway is None:
        return "Розыгрыш не найден."
    elif giveaway.status == GiveawayStatus.PUBLISHED or giveaway.status == GiveawayStatus.NOT_PUBLISHED:
        return "Розыгрыш ещё не завершён."
    else:
        # Получаем количество участников
        participant_count = await redis_get_participants_count(giveaway_id)

        # Генерация текста о конкурсе
        initial_text = (f"Розыгрыш №{giveaway_id}\n"
                        f"<a href='{giveaway.post_url}'>Ссылка на розыгрыш</a>\n"
                        f"Кол-во участников: {participant_count}\n"
                        f"Кол-во победителей: {giveaway.winners_count}\n")

        # Проверяем, как завершился конкурс
        if giveaway.end_count is not None:
            initial_text += f"Розыгрыш завершен по кол-ву участников: {giveaway.end_count}\n"
        elif giveaway.end_datetime is not None:
            initial_text += f"Розыгрыш завершён по времени: {giveaway.end_datetime.strftime('%d.%m.%Y %H:%M')}\n"

        text = "\nРезультаты розыгрыша:\n\nПобедители:\n"
        messages = []
        limit = 4096 - len(initial_text)

        # Добавляем результаты конкурса
        c = 0
        for winner_id in giveaway.winner_ids:
            c += 1
            winner_text = f"{c}.{await get_user_creds(winner_id)}\n"
            if len(text) + len(winner_text) > limit:
                if not messages:
                    messages.append(initial_text + text)
                else:
                    messages.append(text)
                text = ""
                limit = 4096
            text += winner_text

        if text:
            messages.append(text)

        return messages


async def get_giveaway_post(giveaway, user_id):
    text = giveaway.text
    buttons = {f"{giveaway.button}": f"{await join_giveaway_link(giveaway.id)}"}
    text += "\n\n<b>Условия участия:</b>\n\n"
    message = None

    if not giveaway.sponsor_channel_ids or giveaway.channel_id not in giveaway.sponsor_channel_ids:
        channel = await channel_info(channel_id=giveaway.channel_id)
        text += await channel_conditions_text(channel)

    if giveaway.sponsor_channel_ids:
        for channel_id in giveaway.sponsor_channel_ids:
            try:
                channel = await channel_info(channel_id=channel_id)
                text += await channel_conditions_text(channel)
            except TelegramBadRequest:
                text += f"✅ Подпишись на (бота удалили из канала)\n"

    if giveaway.extra_conditions:
        text += f"\n{giveaway.extra_conditions}\n\n"

    if giveaway.end_datetime:
        text += (f"\nРезультаты розыгрыша: "
                 f"<b>{giveaway.end_datetime.strftime('%d.%m.%Y %H:%M')}</b>\n\n")
    else:
        text += f"\nРезультаты розыгрыша будут при достижении <b>{giveaway.end_count} участника(ов)</b>\n\n"

    if giveaway.media_type:
        if giveaway.media_type == "photo":
            message = await bot.send_photo(chat_id=user_id, photo=giveaway.media, caption=text,
                                           reply_markup=await get_callback_btns(btns=buttons))
        elif giveaway.media_type == "video":
            message = await bot.send_video(chat_id=user_id, video=giveaway.media, caption=text,
                                           reply_markup=await get_callback_btns(btns=buttons))
        elif giveaway.media_type == "animation":
            message = await bot.send_animation(chat_id=user_id, animation=giveaway.media, caption=text,
                                               reply_markup=await get_callback_btns(btns=buttons))
    else:
        message = await bot.send_message(chat_id=user_id, text=text,
                                         reply_markup=await get_callback_btns(btns=buttons))
    return message

import asyncio
import datetime
from random import shuffle
from sqlalchemy import declarative_transactional as transactional


import pytz
from aiogram.exceptions import TelegramBadRequest

from create_bot import bot
from db.pg_engine import session_maker
from db.pg_models import GiveawayStatus
from db.pg_orm_query import orm_get_giveaway_by_id, orm_get_due_giveaways, \
    orm_update_giveaway_status, orm_update_giveaway_post_data, orm_add_winners, orm_update_participants_count
from db.r_operations import redis_create_giveaway, redis_get_participants, redis_expire_giveaway, \
    redis_get_participants_count
from tools.giveaway_utils import post_giveaway, giveaway_post_notification, giveaway_result_notification, \
    update_giveaway_message, winners_notification
from tools.texts import encode_giveaway_id
from tools.utils import convert_id, is_subscribed, get_bot_link_to_start, get_user_creds

session = session_maker()


async def publish_giveaway(giveaway_id):
    giveaway = await orm_get_giveaway_by_id(session, giveaway_id)
    if giveaway:
        message = await post_giveaway(giveaway)

        # Формируем ссылку на отправленное сообщение
        chat_id = message.chat.id
        clear_chat_id = await convert_id(chat_id)
        message_id = message.message_id
        post_url = f"https://t.me/c/{clear_chat_id}/{message_id}"
        await giveaway_post_notification(giveaway, post_url)
        await redis_create_giveaway(giveaway.id)
        # Обновляем запись в базе данных
        await orm_update_giveaway_status(session, giveaway_id, GiveawayStatus.PUBLISHED)
        await orm_update_giveaway_post_data(session, giveaway_id, post_url, message_id)


@transactional
async def publish_giveaway_results(giveaway_id):
    giveaway = await orm_get_giveaway_by_id(session, giveaway_id)
    msg_id = giveaway.message_id
    await update_giveaway_message(session, giveaway.id, giveaway.channel_id, giveaway.message_id)
    await asyncio.sleep(1 / 20)

    if giveaway and giveaway.status != GiveawayStatus.FINISHED:
        # Получаем всех участников
        participants = await redis_get_participants(giveaway_id)
        if not participants:
            message = await bot.send_message(reply_to_message_id=msg_id, chat_id=giveaway.channel_id,
                                             text="Розыгрыш завершен, но участников нет.")
            await giveaway_result_notification(message, giveaway)

            await orm_update_giveaway_status(session, giveaway.id, GiveawayStatus.FINISHED)
            return

        # Перемешиваем список участников для случайного выбора
        shuffle(participants)

        winners = []
        for user_id in participants:
            if await is_subscribed(giveaway.sponsor_channel_ids, user_id):
                winners.append(user_id)
                if len(winners) == giveaway.winners_count:
                    break

        # Сообщение о завершении розыгрыша
        if winners:
            winner_mentions = []
            c = 0
            for winner in winners:
                c += 1
                winner_mentions.append(f"{c}.{await get_user_creds(winner)}")

                # chat = await bot.get_chat(winner)
                # user_name = chat.first_name if chat.first_name else "No name"
                # user_username = f"@{chat.username}" if chat.username else f"{winner}"
                # winner_mentions.append(f"{c}.<a href='tg://user?id={winner}'>{user_name}</a> ({user_username})")

            giveaway_end_text = f"Розыгрыш завершен!\n\nПобедители:\n{'\n'.join(winner_mentions)}\n\n"
        else:
            giveaway_end_text = "Розыгрыш завершен, но подходящих победителей нет.\n\n"

        g_id = await encode_giveaway_id(giveaway.id)
        verify_link = f"<a href='{await get_bot_link_to_start()}checkgive_{g_id}'>Проверить результаты</a>"
        giveaway_end_text += verify_link
        try:
            message = await bot.send_message(reply_to_message_id=msg_id, chat_id=giveaway.channel_id,
                                             text=giveaway_end_text)
            await winners_notification(winners=winners, message=message, link=verify_link)
        except TelegramBadRequest:
            message = await bot.send_message(chat_id=giveaway.channel_id,
                                             text=giveaway_end_text)
        await giveaway_result_notification(message, giveaway)
        await orm_update_giveaway_status(session, giveaway.id, GiveawayStatus.FINISHED)
        if winners:
            await orm_add_winners(session, giveaway.id, winners)
        await orm_update_participants_count(session, giveaway.id, len(participants))
        await redis_expire_giveaway(giveaway.id)


async def schedule_giveaways():
    while True:
        current_time = datetime.datetime.now(pytz.timezone('Europe/Moscow')).replace(tzinfo=None)

        not_published, ready_for_results = await orm_get_due_giveaways(session, current_time)

        if not not_published and not ready_for_results:
            continue
        else:
            for giveaway in not_published:
                giveaway_post_datetime = giveaway.post_datetime.replace(tzinfo=None) if giveaway.post_datetime else None
                if giveaway_post_datetime <= current_time:
                    await publish_giveaway(giveaway.id)
                    await asyncio.sleep(1 / 20)

            for giveaway in ready_for_results:
                await update_giveaway_message(session, giveaway.id, giveaway.channel_id, giveaway.message_id)
                await asyncio.sleep(1 / 20)
                giveaway_end_datetime = giveaway.end_datetime.replace(tzinfo=None) if giveaway.end_datetime else None
                if giveaway_end_datetime and giveaway_end_datetime <= current_time:
                    await publish_giveaway_results(giveaway.id)
                    await asyncio.sleep(1 / 20)
                    continue

                if giveaway.end_count is not None:
                    participants_count = await redis_get_participants_count(giveaway.id)
                    if participants_count >= giveaway.end_count:
                        await publish_giveaway_results(giveaway.id)
                        await asyncio.sleep(1 / 20)

        await asyncio.sleep(60)


async def start_scheduler():
    await schedule_giveaways()

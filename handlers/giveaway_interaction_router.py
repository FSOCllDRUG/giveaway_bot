import re
from datetime import datetime, timedelta
from random import shuffle

import pytz
from aiogram import Router, F
from aiogram.filters import StateFilter, CommandStart, CommandObject, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, BufferedInputFile, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from create_bot import bot
from db.pg_models import GiveawayStatus
from db.pg_orm_query import orm_get_join_giveaway_data, orm_get_user_giveaways, orm_get_giveaway_by_id, \
    orm_get_giveaway_end_count, orm_delete_giveaway, orm_update_giveaway_end_conditions, orm_add_winners, \
    orm_get_user_data, orm_user_start
from db.r_engine import redis_conn
from db.r_operations import redis_get_participants, redis_get_participants_count
from filters.chat_type import ChatType
from keyboards.inline import get_callback_btns
from keyboards.reply import main_kb
from tools.captcha import generate_captcha
from tools.giveaway_scheduler import publish_giveaway_results
from tools.giveaway_utils import add_participant_and_update_button, check_giveaway_text
from tools.texts import decode_giveaway_id, format_giveaways, datetime_example, encode_giveaway_id
from tools.utils import is_subscribed, get_bot_link_to_start, is_admin

giveaway_interaction_router = Router()
giveaway_interaction_router.message.filter(ChatType("private"))

status_mapping = {
    GiveawayStatus.NOT_PUBLISHED: "⏳ Ждёт публикации",
    GiveawayStatus.PUBLISHED: "✅ Опубликован",
    GiveawayStatus.FINISHED: "❌ Завершён"
}


class Captcha(StatesGroup):
    giveaway_id = State()
    awaiting_captcha = State()
    attempts_left = State()


@giveaway_interaction_router.message(
    CommandStart(deep_link=True, magic=F.args.regexp(re.compile(r'join_giveaway_(.+)'))),
    StateFilter(None))
async def start_join_giveaway(message: Message, command: CommandObject, session: AsyncSession, state: FSMContext):
    encoded_id = command.args.split("_")[-1]
    giveaway_id = await decode_giveaway_id(encoded_id)
    if await orm_get_user_data(session, user_id=message.from_user.id) is None:
        await orm_user_start(session, data={
            "user_id": message.from_user.id,
            "username": message.from_user.username if message.from_user.username is not None else None,
            "name": message.from_user.full_name,
        })
    giveaway = await orm_get_giveaway_by_id(session=session, giveaway_id=giveaway_id)
    if giveaway is None:
        await message.answer("Розыгрыш не найден.", reply_markup=await main_kb(await is_admin(message.from_user.id)))
        return
    elif giveaway.status == GiveawayStatus.FINISHED:
        await message.answer("Розыгрыш уже завершён.", reply_markup=await main_kb(await is_admin(message.from_user.id)))
        return
    user_id = message.from_user.id
    if user_id in await redis_get_participants(giveaway_id):
        await message.answer(f"❗️Вы уже участвуете в этом розыгрыше.",
                             reply_markup=await main_kb(await is_admin(message.from_user.id)))
        return
    sponsor_channels, captcha, end_count = await orm_get_join_giveaway_data(session=session,
                                                                            giveaway_id=giveaway_id)

    if await is_subscribed(channels=sponsor_channels, user_id=user_id) == False:
        await message.answer(
            f"Чтобы участвовать в розыгрыше, <b><u>Вам необходимо подписаться</u></b> на все "
            f"указанные каналы в условиях.",
            reply_markup=await main_kb(await is_admin(message.from_user.id)))
        return

    if captcha:
        captcha_text, captcha_image = await generate_captcha()
        await message.answer("❗️<b>Перед тем, как Вы станете участником розыгрыша, Мы должны убедиться, "
                             "что Вы не бот.</b>")
        await redis_conn.setex(f"captcha:{user_id}", 300, captcha_text)  # Save captcha in redis with a TTL
        input_file = BufferedInputFile(captcha_image.getvalue(), filename=f"captcha{user_id}.png")
        await message.answer_photo(photo=input_file, caption="❓Какие числа Вы видите на картинке? Отправьте боту "
                                                             "ответ!\n\n"
                                                             "<b>Для отказа от участия в розыгрыше нажмите</b> /cancel")
        await state.set_state(Captcha.awaiting_captcha)
        await state.update_data(giveaway_id=giveaway_id, chat_id=message.chat.id, message_id=message.message_id)
    else:
        await add_participant_and_update_button(session, giveaway_id, user_id, giveaway.channel_id, giveaway.message_id)
        await state.clear()
        await message.answer(f"🎉 <b>Поздравляем!</b>\n"
                             f"<b>Теперь Вы участник розыгрыша #{giveaway_id}!</b>",
                             reply_markup=await main_kb(await is_admin(message.from_user.id)))
        if end_count:
            if await redis_get_participants_count(giveaway_id) >= end_count:
                await publish_giveaway_results(giveaway_id)


@giveaway_interaction_router.message(
    CommandStart(deep_link=True, magic=F.args.regexp(re.compile(r'checkgive_(.+)'))),
    StateFilter(None))
async def start_check_giveaway(message: Message, command: CommandObject, session: AsyncSession):
    encoded_id = command.args.split("_")[-1]
    giveaway_id = await decode_giveaway_id(encoded_id)
    giveaway = await orm_get_giveaway_by_id(session=session, giveaway_id=giveaway_id)
    if await orm_get_user_data(session, user_id=message.from_user.id) is None:
        await orm_user_start(session, data={
            "user_id": message.from_user.id,
            "username": message.from_user.username if message.from_user.username is not None else None,
            "name": message.from_user.full_name,
        })
    if giveaway is None:
        await message.answer("Розыгрыш не найден.",
                             reply_markup=await main_kb(await is_admin(message.from_user.id)))
        return
    elif giveaway.status == GiveawayStatus.PUBLISHED or giveaway.status == GiveawayStatus.NOT_PUBLISHED:
        await message.answer("Розыгрыш ещё не завершён.",
                             reply_markup=await main_kb(await is_admin(message.from_user.id)))
    else:
        await message.answer(text=await check_giveaway_text(session=session, giveaway_id=giveaway_id),
                             reply_markup=await main_kb(await is_admin(message.from_user.id)))
        return


@giveaway_interaction_router.message(StateFilter(Captcha.awaiting_captcha))
async def check_captcha(message: Message, state: FSMContext, session: AsyncSession):
    user_id = message.from_user.id
    user_input = message.text

    captcha_text = await redis_conn.get(f"captcha:{user_id}")
    data = await state.get_data()
    attempts_left = data.get('attempts_left', 3)

    if captcha_text and user_input == captcha_text:
        await message.answer("✅ Капча пройдена успешно!",
                             reply_markup=await main_kb(await is_admin(message.from_user.id)))
        data = await state.get_data()
        giveaway_id = data.get('giveaway_id')
        giveaway = await orm_get_giveaway_by_id(session=session, giveaway_id=giveaway_id)
        await add_participant_and_update_button(session, giveaway_id, user_id, giveaway.channel_id, giveaway.message_id)
        await message.answer(f"🎉 <b>Поздравляем!</b>\n"
                             f"<b>Теперь Вы участник розыгрыша #{giveaway_id}!</b>")
        await state.clear()
        await add_participant_and_update_button(session, giveaway_id, user_id, message.chat.id, message.message_id)
        await redis_conn.delete(f"captcha:{user_id}")
        end_count = await orm_get_giveaway_end_count(session, giveaway_id)
        if end_count:
            if await redis_get_participants_count(giveaway_id) >= end_count:
                await publish_giveaway_results(giveaway_id)
    else:
        attempts_left -= 1
        if attempts_left > 0:
            await message.answer(f"Неправильный текст капчи. Попробуйте еще раз. Осталось попыток: {attempts_left}")
            await state.update_data(attempts_left=attempts_left)
        else:
            await message.answer("Вы исчерпали все попытки. Попробуйте снова позже.",
                                 reply_markup=await main_kb(await is_admin(message.from_user.id)))
            await state.clear()
            await redis_conn.delete(f"captcha:{user_id}")


@giveaway_interaction_router.message(F.text == "Мои розыгрыши")
@giveaway_interaction_router.message(Command("my_gives"))
async def my_gives(message: Message, session: AsyncSession):
    my_givs = await format_giveaways(await orm_get_user_giveaways(session=session, user_id=message.from_user.id))
    initial_text = "🎁<b>Ваши розыгрыши!</b>\n\n"
    text = initial_text
    messages = []
    limit = 4096

    if not my_givs:
        await message.answer("❌ У вас нет розыгрышей!")
        return

    for giv in my_givs:
        giv_text = f"{giv}\n"
        if len(text) + len(giv_text) > limit:
            messages.append(text)
            text = initial_text + giv_text
        else:
            text += giv_text

    messages.append(text)

    for msg in messages:
        await message.answer(msg)


@giveaway_interaction_router.message(F.text.startswith("/mygive"))
async def my_giveaway_details(message: Message, session: AsyncSession):
    giveaway_id = int(message.text.split("/mygive")[1].strip())
    user_id = message.from_user.id

    # Получаем данные о розыгрыше
    giveaway = await orm_get_giveaway_by_id(session=session, giveaway_id=giveaway_id)

    if not giveaway or giveaway.user_id != user_id:
        await message.answer(f"❌ Розыгрыш №{giveaway_id} не найден или у вас нет к нему доступа.")
        return

    status = status_mapping.get(giveaway.status, "Неизвестный статус")
    post_url = giveaway.post_url
    participants_count = giveaway.participants_count if status == "Завершён" else await redis_get_participants_count(
        giveaway_id)
    winners_count = giveaway.winners_count
    end_count = giveaway.end_count
    end_datetime = giveaway.end_datetime.strftime('%d.%m.%Y %H:%M') if giveaway.end_datetime else None
    post_datetime = giveaway.post_datetime.strftime('%d.%m.%Y %H:%M')
    text = (f"<b>Розыгрыш №</b>{giveaway_id}\n"
            f"Статус: {status}\n"
            f"Сообщение с розыгрышем: <a href='{post_url}'>Ссылка</a>\n"
            f"Количество участников: {participants_count}\n"
            f"Количество победителей: {winners_count}\n"
            f"Время публикации: {post_datetime}\n")

    if end_count:
        text += f"Завершение при количестве участников: {end_count}\n"
    if end_datetime:
        text += f"Время завершения: {end_datetime}\n"
    btns = {}
    if status == "⏳ Ждёт публикации" or status == "✅ Опубликован":
        btns.update({"Изменить условия завершения розыгрыша": f"change_end_condition_{giveaway_id}"})
    if status == "✅ Опубликован":
        btns.update({"Подвести итоги прямо сейчас": f"finish_giveaway_{giveaway_id}"})
    if status == "❌ Завершён":
        btns.update({"Получить ссылку на результаты": f"get_result_link_{giveaway_id}"})
        btns.update({"Выбрать дополнительных победителей": f"add_winners_{giveaway_id}"})
    btns.update({"Удалить розыгрыш": f"delete_giveaway_{giveaway_id}"})
    await message.answer(text, reply_markup=await get_callback_btns(btns=btns, sizes=(1,)))


@giveaway_interaction_router.callback_query(F.data.startswith("delete_giveaway_"))
async def delete_giveaway(callback: CallbackQuery):
    await callback.answer("")
    g_id = int(callback.data.split("_")[-1])
    await callback.message.answer("Вы уверены, что хотите удалить розыгрыш?", reply_markup=await get_callback_btns(
        btns={"Да": f"sure_delete_giveaway_{g_id}", "Нет": "cancel"}, sizes=(1,)))


@giveaway_interaction_router.callback_query(F.data.startswith("sure_delete_giveaway_"))
async def delete_giveaway_sure(callback: CallbackQuery, session: AsyncSession):
    await callback.answer("")
    g_id = int(callback.data.split("_")[-1])
    await orm_delete_giveaway(session=session, giveaway_id=g_id)
    await callback.message.delete()
    await callback.message.answer("✅ Розыгрыш успешно удален.")


class EndCondition(StatesGroup):
    giveaway_id = State()
    data = State()


@giveaway_interaction_router.callback_query(F.data.startswith("change_end_condition_"))
async def change_end_condition(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    g_id = int(callback.data.split("_")[-1])
    await state.update_data(giveaway_id=g_id)
    await state.set_state(EndCondition.giveaway_id)
    await callback.message.answer("🗓 Как завершить розыгрыш?",
                                  reply_markup=await get_callback_btns(
                                      btns={"По кол-ву участников": "change_end_count",
                                            "По времени": "change_end_time",
                                            "Отмена": "cancel"},
                                      sizes=(1,)
                                  ))


@giveaway_interaction_router.callback_query(F.data == "change_end_count",
                                            StateFilter(EndCondition.giveaway_id))
async def change_end_count(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    await callback.message.answer("🏁 Укажите количество участников для проведения розыгрыша:\n\n",
                                  reply_markup=await get_callback_btns(
                                      btns={"Отмена": "cancel"},
                                      sizes=(1,)
                                  ))
    await state.set_state(EndCondition.data)


@giveaway_interaction_router.message(StateFilter(EndCondition.data), F.text.isdigit())
async def change_end_count_data(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    p_count = await redis_get_participants_count(data.get('giveaway_id'))
    if int(message.text) > p_count:
        giveaway_id = data.get('giveaway_id')
        end_count = int(message.text)
        await orm_update_giveaway_end_conditions(session=session, giveaway_id=giveaway_id, end_count=end_count,
                                                 end_datetime=None)
        await message.answer("🎉 Количество участников для проведения розыгрыша изменено!")
        await state.clear()
    else:
        await message.answer(f"❌ Количество участников не может быть меньше {p_count}!")


@giveaway_interaction_router.callback_query(F.data == "change_end_time",
                                            StateFilter(EndCondition.giveaway_id))
async def change_end_datetime(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    await callback.message.answer("🏁 Когда нужно определить победителя? (Укажите время в формате дд.мм.гг чч:мм)"
                                  "\n\n"
                                  "Бот живет по времени (GMT+3) Москва, Россия",
                                  reply_markup=await get_callback_btns(
                                      btns={"Отмена": "cancel"},
                                      sizes=(1,)
                                  ))
    await callback.message.answer(text=await datetime_example())
    await state.set_state(EndCondition.data)


@giveaway_interaction_router.message(StateFilter(EndCondition.data), F.text)
async def change_end_time_data(message: Message, state: FSMContext, session: AsyncSession):
    try:
        data = await state.get_data()
        # Установка временной зоны Москва (GMT+3)
        moscow_tz = pytz.timezone('Europe/Moscow')

        # Преобразование user_datetime в aware datetime в зоне GMT+3
        user_datetime = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        user_datetime = moscow_tz.localize(user_datetime)

        # Получение текущего времени в зоне GMT+3
        current_time = datetime.now(moscow_tz)
        # Проверяем, что время публикации не ранее чем через 5 минут от текущего времени
        if user_datetime < current_time + timedelta(minutes=5):
            await message.answer("❌Дата и время должны быть не раньше чем через 5 минут от текущего времени!")
            return

        end_time = user_datetime.replace(tzinfo=None).isoformat()
        await orm_update_giveaway_end_conditions(session=session, giveaway_id=data.get('giveaway_id'), end_count=None,
                                                 end_datetime=end_time)
        await message.answer("✅Время для подведения результатов сохранено")
        await state.clear()
    except ValueError:
        await message.answer("❌Некорректный формат <b><u>дата и времени</u></b>!")


@giveaway_interaction_router.callback_query(F.data.startswith("finish_giveaway_"))
async def finish_giveaway(callback: CallbackQuery):
    await callback.answer("")
    giveaway_id = int(callback.data.split("_")[-1])
    await callback.message.answer("Вы уверены, что хотите завершить розыгрыш?",
                                  reply_markup=await get_callback_btns(
                                      btns={"Да": f"yes_finish_giveaway_{giveaway_id}",
                                            "Нет": f"cancel"},
                                  ))


@giveaway_interaction_router.callback_query(F.data.startswith("yes_finish_giveaway_"))
async def finish_giveaway_sure(callback: CallbackQuery):
    await callback.answer("")
    giveaway_id = int(callback.data.split("_")[-1])
    await callback.message.answer("Заканчиваем розыгрыш...")
    await publish_giveaway_results(giveaway_id)


@giveaway_interaction_router.callback_query(F.data.startswith("get_result_link_"))
async def get_result_link(callback: CallbackQuery):
    await callback.answer("")
    giveaway_id = int(callback.data.split("_")[-1])
    g_id = await encode_giveaway_id(giveaway_id)
    await callback.message.answer("Эту ссылку вы можете опубликовать в канале в "
                                  "подтверждение честности проведенного розыгрыша:\n\n"
                                  f"<code>{await get_bot_link_to_start()}checkgive_{g_id}</code>")


class AddWinners(StatesGroup):
    giveaway_id = State()


@giveaway_interaction_router.callback_query(F.data.startswith("add_winners_"))
async def add_winners(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    giveaway_id = int(callback.data.split("_")[-1])
    await state.update_data(giveaway_id=giveaway_id)
    await state.set_state(AddWinners.giveaway_id)
    await callback.message.answer("❗️<b>Примечание:</b>\n"
                                  "Список участников розыгрыша хранится <b>7 ДНЕЙ</b> после его завершения!\n\n"
                                  "🏁 Укажите количество дополнительных победителей:",
                                  reply_markup=await get_callback_btns(
                                      btns={"Отмена": "cancel"},
                                      sizes=(1,)
                                  ))


@giveaway_interaction_router.message(StateFilter(AddWinners.giveaway_id), F.text.isdigit())
async def add_winners_data(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    giveaway_id = data.get('giveaway_id')
    await message.answer("✅Количество дополнительных победителей сохранено")
    giveaway = await orm_get_giveaway_by_id(session=session, giveaway_id=giveaway_id)
    add_win_count = int(message.text)
    participants = await redis_get_participants(giveaway_id)
    if not participants:
        await message.answer(reply_to_message_id=message.message_id, chat_id=message.from_user.id,
                             text="Нет участников для выбора.")
        return

    # Перемешиваем список участников для случайного выбора
    shuffle(participants)

    winners = []
    for user_id in participants:
        if (await is_subscribed(giveaway.sponsor_channel_ids, user_id)) and user_id not in giveaway.winner_ids:
            winners.append(user_id)
            if len(winners) == add_win_count:
                break

    if not winners:
        await message.answer(reply_to_message_id=message.message_id,
                             text="Не нашлось участников, выполнивших условия розыгрыша, "
                                  "дополнительных победителей нет!")
    if winners:
        text = ""
        c = 0
        for winners_id in winners:
            c += 1
            chat = await bot.get_chat(winners_id)
            user_name = chat.first_name if chat.first_name else "No name"
            user_username = f"@{chat.username}" if chat.username else ""
            text += f"\n{c}.<a href='tg://user?id={winners_id}'>{user_name}</a> ({user_username})"
        await message.answer(reply_to_message_id=message.message_id,
                             text=f"Выбор дополнительных победителей завершен!\n{text}")
        await orm_add_winners(session=session, giveaway_id=giveaway_id, new_winners=winners)
    await state.clear()

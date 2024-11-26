import asyncio
import datetime
from collections import defaultdict

import pytz
from aiogram import Router, F
from aiogram.filters import StateFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from create_bot import bot
from db.pg_orm_query import orm_get_channels_for_admin
# from db.pg_orm_query import (
#     orm_add_participant, orm_get_sponsor_channels, orm_end_giveaway, orm_get_max_participants,
#     orm_get_channels_for_admin
# )
# from db.r_operations import redis_add_participant, redis_get_participants_count, redis_is_subscribed
from keyboards.inline import get_callback_btns, captcha_toggle
from middlewares.activity_middleware import ActivityMiddleware
from tools.utils import channel_info, datetime_example, get_giveaway_preview, get_channel_hyperlink, \
    get_giveaway_info_text, captcha_on_text, captcha_off_text

# import re

giveaway_router = Router()
giveaway_router.message.middleware(ActivityMiddleware())

# @giveaway_router.message(CommandStart(deep_link=True, magic=F.args.regexp(re.compile(r'join_giveaway_(\d+)'))))
# async def start_join_giveaway(message: Message, command: CommandObject, session: AsyncSession, state: FSMContext):
#     giveaway_id = int(command.args.split("_")[-1])
#     user_id = message.from_user.id
#
#     sponsor_channels = await orm_get_sponsor_channels(session, giveaway_id)
#     for channel in sponsor_channels:
#         if not await redis_is_subscribed(user_id, channel.channel_id):
#             await message.answer(f"Вы должны подписаться на {channel.channel_id} чтобы участвовать в розыгрыше.")
#             return
#
#     await orm_add_participant(session, user_id, giveaway_id)
#     await redis_add_participant(giveaway_id, user_id)
#
#     participants_count = await redis_get_participants_count(giveaway_id)
#     max_participants = await orm_get_max_participants(session, giveaway_id)
#
#     if max_participants and participants_count >= max_participants:
#         await orm_end_giveaway(session, giveaway_id)
#         await message.answer(f"Розыгрыш завершен, так как достигнуто максимальное количество участников.")
#         return
#
#     await message.answer(f"🎉 Теперь вы участник розыгрыша No{giveaway_id}")
#     await state.clear()

user_locks = defaultdict(asyncio.Lock)


class CreateGiveaway(StatesGroup):
    media_type = State()
    media = State()
    text = State()
    button = State()
    sponsor_channels = State()
    winners_count = State()
    channel_id = State()
    extra_conditions = State()
    post_datetime = State()
    end_datetime = State()
    end_count = State()
    captcha = State()
    media_group_id = State()  # To avoid sending warning about "only one media" more than once


@giveaway_router.message(Command("new_giveaway"))
@giveaway_router.message(F.text == "Создать розыгрыш")
async def create_giveaway(message: Message, state: FSMContext, session: AsyncSession):
    if not await orm_get_channels_for_admin(session=session, admin_user_id=message.from_user.id):
        await message.answer("❌У вас нет каналов/групп для создания розыгрыша.\n\n"
                             "Чтобы перейти к добавлению канала/группы"
                             " введите /my_channels")
        return
    else:
        await state.clear()
        await state.set_state(CreateGiveaway.media_type)
        await message.answer("<b>СОЗДАНИЕ РОЗЫГРЫША!</b>\n\n"
                             "Отправьте текст для розыгрыша.\n"
                             "Вы можете также отправить вместе с текстом картинку, видео или GIF!\n\n"
                             "<b>❗️Важно:</b>\n"
                             "<i>Вы можете использовать только 1 медиафайл.</i>",
                             reply_markup=await get_callback_btns(btns={"Отмена": "cancel"}))
    # await state.update_data(media_warned=0)


@giveaway_router.message(StateFilter(CreateGiveaway.media_type))
async def create_giveaway_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    async with user_locks[user_id]:
        data = await state.get_data()
        media_group_id = data.get("media_group_id")

        # Проверяем наличие media_group_id в сообщении
        if message.media_group_id:
            # Если предупреждение для этого media_group_id уже было отправлено, не отправляем его повторно
            if media_group_id == message.media_group_id:
                return
            # Обновляем состояние с новым media_group_id и предупреждаем о медиагруппе
            await state.update_data(media_group_id=message.media_group_id)
            await message.answer("❗️Важно:\nВы можете использовать только 1 медиафайл.")
            return
        else:
            # Если сообщение не из медиагруппы, сбрасываем переменную
            await state.update_data(media_group_id=None)

    await state.update_data(message=message.message_id)
    if message.photo:
        media_id = message.photo[-1].file_id
        await state.update_data(media_type="photo")
        await message.answer("✅Фото успешно добавлено!")
    elif message.video:
        media_id = message.video.file_id
        await message.answer("✅Видео успешно добавлено!")
        await state.update_data(media_type="video")

    elif message.animation:
        media_id = message.animation.file_id
        await message.answer("✅GIF успешно добавлен!")
        await state.update_data(media_type="animation")
    else:
        media_id = None

    if media_id is not None:
        await state.update_data(media=media_id)
    if message.text:
        text = message.html_text
        await message.answer("✅Текст успешно добавлен!")
    elif message.caption:
        text = message.html_text
        await message.answer("✅Текст успешно добавлен!")
    else:
        text = ""
    await state.update_data(text=text)
    await state.set_state(CreateGiveaway.button)
    await message.answer("Отправьте текст,который вы хотите видеть на кнопке.\n"
                         "Либо выберите один из вариантов ниже:",
                         reply_markup=await get_callback_btns(btns={"Участвовать": "join_1",
                                                                    "Участвую!": "join_2",
                                                                    "Принять участие": "join_3",
                                                                    }))


@giveaway_router.callback_query(StateFilter(CreateGiveaway.button), F.data.startswith("join_"))
async def create_giveaway_button(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    join = int(callback.data.split("_")[-1])
    if join == 1:
        button = "Учавствовать"
    elif join == 2:
        button = "Учавствовать!"
    else:
        button = "Принять участие"
    await state.update_data(button=button)
    await state.set_state(CreateGiveaway.sponsor_channels)
    await callback.message.answer("✅Текст кнопки успешно сохранен!")
    await callback.message.answer("❗️Добавьте каналы, на которые пользователям нужно будет"
                                  "подписаться для участия в розыгрыше.\n"
                                  "<b>Подписка на канал, в котором проводится розыгрыш, "
                                  "обязательна и включена по умолчанию.</b>\n\n"

                                  "Чтобы добавить канал, нужно:\n"
                                  "1. <b>Добавить бота</b> (@WinGiveBot) в ваш канал <u>в роли администратора</u> (это "
                                  "нужно, чтобы бот мог проверить подписан ли пользователь на канал).\n"
                                  "2. <b>Отправить боту канал в формате</b> @channelname "
                                  "(или переслать пост из канала).\n\n"

                                  "⚠️<b>Если вы хотите, чтобы участие в розыгрыше было без подписок на канал, "
                                  "нажмите кнопку ниже:</b>",
                                  reply_markup=await get_callback_btns(
                                      btns={"Розыгрыш без обязательных подписок": "finish_sponsors"}))


@giveaway_router.message(StateFilter(CreateGiveaway.button), F.text)
async def create_giveaway_own_button(message: Message, state: FSMContext):
    await state.update_data(button=message.text)
    await state.set_state(CreateGiveaway.sponsor_channels)
    await message.answer("✅Текст кнопки успешно сохранен!")
    await message.answer("❗️Добавьте каналы, на которые пользователям нужно будет"
                         "подписаться для участия в розыгрыше.\n"
                         "<b>Подписка на канал, в котором проводится розыгрыш, "
                         "обязательна и включена по умолчанию.</b>\n\n"
                         "Чтобы добавить канал, нужно:\n"
                         "1. <b>Добавить бота</b> (@WinGiveBot) в ваш канал <u>в роли администратора</u> (это "
                         "нужно, чтобы бот мог проверить подписан ли пользователь на канал).\n"
                         "2. <b>Отправить боту канал в формате</b> @channelname "
                         "(или переслать пост из канала).\n\n"

                         "⚠️<b>Если вы хотите, чтобы участие в розыгрыше было без подписок на канал, "
                         "нажмите кнопку ниже:</b>",
                         reply_markup=await get_callback_btns(
                             btns={"Розыгрыш без обязательных подписок": "finish_sponsors"}))


@giveaway_router.message(StateFilter(CreateGiveaway.sponsor_channels))
async def create_giveaway_sponsor_channels(message: Message, state: FSMContext):
    if message.text.startswith("@"):
        channel_name = message.text
        try:
            chat = await bot.get_chat(channel_name)
            if not chat:
                await message.answer("❌Канал не найден!")
                return
            if not (await chat.get_member(bot.id)).can_manage_chat:
                await message.answer(
                    f"❌Для добавления канала {channel_name} бот должен быть админом в этом канале.")
                return
            data = await state.get_data()
            if "sponsor_channels" not in data:
                data["sponsor_channels"] = []
            data["sponsor_channels"].append(chat.id)
            await state.set_data(data)
            data = await state.get_data()
            ch_text = (f"✅Канал {channel_name} добавлен, Вы можете добавить еще один или продолжить создание "
                       f"конкурса!"
                       "Чтобы добавить еще каналы, просто присылайте на них ссылки."
                       "\n\n")
            if "sponsor_channels" in data:
                c = 1
                ch_text += "Добавленные каналы:\n"
                for channel in data["sponsor_channels"]:
                    ch_text += f"{c}) {await get_channel_hyperlink(channel)}\n"
                    c += 1
            ch_text += ("\n<b>❗️Важно:</b>\n"
                        "Не забирайте у бота права администратора канала, иначе"
                        "проверка подписки происходить не будет!")
            if "sponsor_channels" in data:
                for channel in data["sponsor_channels"]:
                    channel_text = "Добавленные каналы:\n"
                    channel_text += f"{await get_channel_hyperlink(channel)}\n"
            await message.answer(text=ch_text,
                                 reply_markup=await get_callback_btns(
                                     btns={"Достаточно каналов,двигаемся дальше!": "finish_sponsors"}))
        except Exception:
            await message.answer("❌Ошибка при добавлении канала!")
    elif message.forward_from_chat:
        channel_id = message.forward_from_chat.id
        chat_info = await channel_info(channel_id)
        try:
            chat = await bot.get_chat(channel_id)
            if not chat:
                await message.answer("❌Канал не найден!")
                return
            if not (await chat.get_member(bot.id)).can_manage_chat:
                await message.answer(
                    f"❌Для добавления канала {chat_info.title} бот должен быть админом в этом канале.")
                return
            data = await state.get_data()
            if "sponsor_channels" not in data:
                data["sponsor_channels"] = []
            data["sponsor_channels"].append(chat.id)
            await state.set_data(data)
            data = await state.get_data()
            ch_text = (f"✅Канал {chat_info.title} добавлен, Вы можете добавить еще один или продолжить создание "
                       f"конкурса!"
                       "Чтобы добавить еще каналы, просто присылайте на них ссылки."
                       "\n\n")
            if "sponsor_channels" in data:
                c = 1
                ch_text += "Добавленные каналы:\n"
                for channel in data["sponsor_channels"]:
                    ch_text += f"{c}) {await get_channel_hyperlink(channel)}\n"
                    c += 1
            ch_text += ("\n<b>❗️Важно:</b>\n"
                        "Не забирайте у бота права администратора канала, иначе"
                        "проверка подписки происходить не будет!")
            await message.answer(text=ch_text,
                                 reply_markup=await get_callback_btns(
                                     btns={"Достаточно каналов,двигаемся дальше!": "finish_sponsors"}))
        except Exception:
            await message.answer("❌Ошибка при добавлении канала!")
    else:
        await message.answer("❌Ты чего-то не то прислал О_о")


@giveaway_router.callback_query(StateFilter(CreateGiveaway.sponsor_channels), F.data == "finish_sponsors")
async def set_winners_count(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    await state.set_state(CreateGiveaway.winners_count)
    await callback.message.answer("🎲Сколько победителей выбрать боту?")


@giveaway_router.message(StateFilter(CreateGiveaway.winners_count))
async def set_winners_count(message: Message, state: FSMContext, session: AsyncSession):
    if message.text.isdigit() and int(message.text) > 0:
        count = int(message.text)
        await state.update_data(winners_count=count)
        await message.answer(f"✅Количество победителей успешно сохранено: {count}")

        user_id = message.from_user.id
        channels = await orm_get_channels_for_admin(session, user_id)
        btns = {}
        for channel in channels:
            chat = await bot.get_chat(channel.channel_id)
            btns[chat.title] = f"giv_channel_{channel.channel_id}"

        await state.set_state(CreateGiveaway.channel_id)
        await message.answer("В каком канале публикуем розыгрыш?",
                             reply_markup=await get_callback_btns(btns=btns, sizes=(1,)))

    else:
        await message.answer("❌Некорректное <b><u>число</u></b> победителей!")


@giveaway_router.callback_query(StateFilter(CreateGiveaway.channel_id), F.data.startswith("giv_channel_"))
async def create_giveaway_channel_id(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    channel_id = int(callback.data.split("_")[-1])
    await state.update_data(channel_id=channel_id)
    await callback.message.answer("✅Канал выбран!")
    await state.set_state(CreateGiveaway.extra_conditions)
    data = await state.get_data()
    text = ""
    text += "<b>Условия участия:</b>\n\n"
    if "sponsor_channels" not in data or data["channel_id"] not in data["sponsor_channels"]:
        channel = await channel_info(data["channel_id"])
        text += f"✅ Подпишись на <a href='{channel.invite_link}'>{channel.title}</a>\n"
    if "sponsor_channels" in data:
        for channel in data["sponsor_channels"]:
            channel = await channel_info(channel)
            text += f"✅ Подпишись на <a href='{channel.invite_link}'>{channel.title}</a>\n"
    # text += "\nНажми на прикрепленную к посту кнопку👇🏻\n\n\n"
    await callback.message.answer(f"Сейчас блок условий выглядит так:\n{text}")
    await callback.message.answer("🟡Примечание:\n"
                                  "При выборе победителей розыгрыша <b><i><u>бот проверяет лишь подписки на указанные "
                                  "каналы!</u></i></b>\n"
                                  "Дополнительные условия ботом <b><i><u>не проверяются</u></i></b>!\n\n"
                                  "📝Нужно ли добавить дополнительные условия помимо подписок на канал(ы)?\n\n"
                                  "Для добавления дополнительных условий отправь текст(доп условий) боту",
                                  reply_markup=await get_callback_btns(btns={
                                      "Без дополнительных условий!": "finish_extra_conditions"
                                  }))


@giveaway_router.message(StateFilter(CreateGiveaway.extra_conditions))
async def get_extra_conditions(message: Message, state: FSMContext):
    await state.update_data(extra_conditions=message.html_text)
    await message.answer("✅Дополнительные условия сохранены!")
    await state.set_state(CreateGiveaway.post_datetime)
    await message.answer("⏰Когда нужно опубликовать розыгрыш?",
                         reply_markup=await get_callback_btns(btns={"Прямо сейчас!": "post_now",
                                                                    "Запланировать публикацию!": "post_plan"}))


@giveaway_router.callback_query(StateFilter(CreateGiveaway.extra_conditions), F.data == "finish_extra_conditions")
async def ask_post_datetime(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    await state.set_state(CreateGiveaway.post_datetime)
    await callback.message.answer("⏰Когда нужно опубликовать розыгрыш?",
                                  reply_markup=await get_callback_btns(btns={"Прямо сейчас!": "post_now",
                                                                             "Запланировать публикацию!": "post_plan"}))


@giveaway_router.callback_query(StateFilter(CreateGiveaway.post_datetime), F.data.startswith("post_"))
async def create_giveaway_post_datetime(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    if callback.data == "post_now":
        await callback.message.answer("✅Розыгрыш будет опубликован сразу после его создания!")
        await callback.message.answer("⌛️Как закончить розыгрыш?",
                                      reply_markup=await get_callback_btns(btns={
                                          "По количеству участников!": "end_count",
                                          "По времени!": "end_time"
                                      }))
        await state.set_state(CreateGiveaway.end_datetime)
    elif callback.data == "post_plan":
        await callback.message.answer("⏰ Когда нужно опубликовать розыгрыш? (Укажите время в формате дд.мм.гг чч:мм)"
                                      "\n\n"
                                      "Бот живет по времени (GMT+3) Москва, Россия")
        await callback.message.answer(text=await datetime_example())


@giveaway_router.message(StateFilter(CreateGiveaway.post_datetime), F.text)
async def set_giveaway_post_datetime(message: Message, state: FSMContext):
    try:
        # Установка временной зоны Москва (GMT+3)
        moscow_tz = pytz.timezone('Europe/Moscow')

        # Преобразование user_datetime в aware datetime в зоне GMT+3
        user_datetime = datetime.datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        user_datetime = moscow_tz.localize(user_datetime)

        # Получение текущего времени в зоне GMT+3
        current_time = datetime.datetime.now(moscow_tz)
        # Проверяем, что время публикации не ранее чем через 5 минут от текущего времени
        if user_datetime < current_time + datetime.timedelta(minutes=5):
            await message.answer("❌Дата и время должны быть не раньше чем через 5 минут от текущего времени!")
            return

        await state.update_data(post_datetime=user_datetime.isoformat())
        await message.answer("✅Время для публикации розыгрыша сохранено!")
        await state.set_state(CreateGiveaway.end_datetime)
        await message.answer("⌛️Как закончить розыгрыш?",
                             reply_markup=await get_callback_btns(btns={
                                 "По времени!": "end_time",
                                 "По количеству участников!": "end_count"
                             }))
    except ValueError:
        await message.answer("❌Некорректный формат <b><u>дата и времени</u></b>!")


@giveaway_router.callback_query(StateFilter(CreateGiveaway.end_datetime), F.data.startswith("end_"))
async def create_giveaway_end_datetime(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    if callback.data == "end_time":
        await state.set_state(CreateGiveaway.end_datetime)
        await callback.message.answer("🔚 ⏰ Когда нужно завершить розыгрыш? (Укажите время в формате дд.мм.гг чч:мм)"
                                      "\n\n"
                                      "Бот живет по времени (GMT+3) Москва, Россия")
        await callback.message.answer(text=await datetime_example())

    elif callback.data == "end_count":
        await state.set_state(CreateGiveaway.end_count)
        await callback.message.answer("🏁 Укажите количество участников для проведения конкурса:"
                                      "\n\n"
                                      "❗️Обратите внимание, участник - тот, кто поучаствовал в конкурсе, "
                                      "выбор будет не по количеству подписчиков канала, "
                                      "а именно по количеству участников (кто нажал на кнопку в конкурсе)")


@giveaway_router.message(StateFilter(CreateGiveaway.end_datetime), F.text)
async def create_giveaway_end_datetime(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        post_datetime_str = data.get("post_datetime")
        moscow_tz = pytz.timezone('Europe/Moscow')

        if post_datetime_str:
            post_datetime = datetime.datetime.fromisoformat(post_datetime_str)
        else:
            post_datetime = None

        user_datetime = datetime.datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        user_datetime = moscow_tz.localize(user_datetime)

        if post_datetime and user_datetime < post_datetime + datetime.timedelta(minutes=1):
            await message.answer("❌Время окончания должно быть не ранее чем через 1 минуту после времени публикации!")
            return

        await state.update_data(end_datetime=user_datetime.isoformat())
        await message.answer("✅Время для подведения результатов сохранено!")
        await message.answer("Превью поста розыгрыша\n"
                             "⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️")
        data = await state.get_data()
        await get_giveaway_preview(data=data, user_id=message.from_user.id, bot=bot)
        await message.answer(text=await get_giveaway_info_text(data),
                             reply_markup=await captcha_toggle("off"))
        await state.set_state(CreateGiveaway.captcha)
    except ValueError:
        await message.answer("❌Некорректный формат <b><u>дата и времени</u></b>!")


@giveaway_router.message(StateFilter(CreateGiveaway.end_count), F.text)
async def create_giveaway_end_count(message: Message, state: FSMContext):
    data = await state.get_data()
    win_count = data.get("winners_count")
    if message.text.isdigit() and int(message.text) != 0 and int(message.text) >= win_count:
        count = int(message.text)
        await state.update_data(end_count=count)
        await message.answer(f"✅ Количество участников для подведения результатов сохранено: {count}")
        data = await state.get_data()
        await state.update_data(captcha=False)
        await message.answer("Превью поста розыгрыша\n"
                             "⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️⬇️")
        await get_giveaway_preview(data=data, user_id=message.from_user.id, bot=bot)
        await message.answer(text=await get_giveaway_info_text(data),
                             reply_markup=await captcha_toggle("off"))
        await state.set_state(CreateGiveaway.captcha)
    else:
        await message.answer("❌Некорректное <b><u>число</u></b> участников!")


@giveaway_router.callback_query(StateFilter(CreateGiveaway.captcha), F.data.startswith("captcha_"))
async def toggle_captcha(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    change_to = str(callback.data.split("_")[-1])
    if change_to == "on":
        await state.update_data(captcha=True)
        new_btns = await captcha_toggle(change_to)
        await callback.message.answer(captcha_on_text)
    else:
        await state.update_data(captcha=False)
        new_btns = await captcha_toggle(change_to)
        await callback.message.answer(captcha_off_text)
    await callback.message.edit_reply_markup(reply_markup=new_btns)


@giveaway_router.callback_query(StateFilter(CreateGiveaway.captcha), F.data == "save_giveaway")
async def create_giveaway_captcha(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    await callback.message.answer("✅Розыгрыш сохранен и готовится к публикации!\n\n"
                                  "Для вызова меню напишите /start")
    # logic for saving to database should be here
    await state.clear()

# @giveaway_router.message()
# async def create_giveaway_default(message: Message):
#     # await message.answer(str(message))
#     print(message)
#     await message.answer(str(message.media_group_id))

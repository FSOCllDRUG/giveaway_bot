from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.ext.asyncio import AsyncSession

from create_bot import bot
from db.pg_orm_query import orm_count_users, orm_get_mailing_list, orm_get_required_channels, orm_is_required_channel, \
    orm_change_required_channel, orm_get_users_with_giveaways, orm_get_user_giveaways, orm_get_giveaway_by_id, \
    orm_get_top_giveaways_by_participants, orm_get_last_giveaway_id
from db.r_operations import (redis_set_mailing_users, redis_set_mailing_msg, redis_set_msg_from,
                             redis_set_mailing_btns, get_active_users_count, redis_get_participants_count)
from filters.chat_type import ChatType
from filters.is_admin import IsAdmin
from handlers.giveaway_interaction_router import status_mapping
from keyboards.inline import get_callback_btns
from keyboards.reply import get_keyboard, admin_kb
from tools.giveaway_utils import get_giveaway_post
from tools.mailing import simple_mailing
from tools.texts import cbk_msg, format_giveaways_for_admin
from tools.utils import msg_to_cbk, channel_info, get_user_creds

admin_private_router = Router()
admin_private_router.message.filter(ChatType("private"), IsAdmin())


@admin_private_router.message(F.text == "Админ панель")
async def get_profile(message: Message, session: AsyncSession):
    async with ChatActionSender.typing(bot=bot, chat_id=message.from_user.id):
        count = await orm_count_users(session)
        required_channels = await orm_get_required_channels(session)
        channels_str = '\n\nОбязательные каналы для функции "Постинг":\n'
        for channel in required_channels:
            chat = await bot.get_chat(channel.channel_id)
            channels_str += f"🔹<a href='{chat.invite_link}'>{chat.title}</a>\n"
        admin_text = (
            f"👥\nВ базе данных <b>{count}</b> человек.. \n"
            f"\n"
            f"🎁\nБыло создано <b>{await orm_get_last_giveaway_id(session)}</b> розыгрышей\n\n"
        )

        active_users_day = await get_active_users_count(1)
        active_users_week = await get_active_users_count(7)
        active_users_month = await get_active_users_count(30)

        admin_text += (f"Количество активных пользователей:\n👥🗓\n"
                       f"День: {active_users_day}\n"
                       f"Неделя: {active_users_week}\n"
                       f"Месяц: {active_users_month}"
                       f"{channels_str}"
                       )
    await message.answer(admin_text, reply_markup=await admin_kb())


@admin_private_router.message(StateFilter("*"), F.text.casefold() == "отмена")
async def cancel_fsm(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Действие отменено.", reply_markup=await admin_kb())


class Mailing(StatesGroup):
    message = State()
    buttons = State()


# Mailing handlers starts
@admin_private_router.message(StateFilter(None), F.text == "Рассылка")
async def make_mailing(message: Message, state: FSMContext):
    await message.answer("Отправь сообщение, которое ты хочешь рассылать\n\n"
                         "<b>ВАЖНО</b>\n\n"
                         "В рассылке может быть приложен только <u>один</u> файл*!\n"
                         "<i>Файл— фото/видео/документ/голосовое сообщение/видео сообщение</i>",
                         reply_markup=get_keyboard("Отмена",
                                                   placeholder="Отправьте сообщение, для рассылки"
                                                   )
                         )
    await state.set_state(Mailing.message)


@admin_private_router.message(StateFilter(Mailing.message))
async def get_message_for_mailing(message: Message, state: FSMContext):
    await state.update_data(message=message.message_id)
    await state.set_state(Mailing.buttons)
    await message.reply("Будем добавлять URL-кнопки к сообщению?", reply_markup=await get_callback_btns(
        btns={"Добавить кнопки": "add_btns",
              "Приступить к рассылке": "confirm_mailing", "Сделать другое сообщение для рассылки": "cancel_mailing"}
    )
                        )


@admin_private_router.callback_query(StateFilter(Mailing.buttons), F.data == "add_btns")
async def add_btns_mailing(callback: CallbackQuery):
    await callback.answer("")
    await callback.message.answer(cbk_msg)


@admin_private_router.message(StateFilter(Mailing.buttons), F.text.contains(":"))
async def btns_to_data(message: Message, state: FSMContext):
    await state.update_data(buttons=await msg_to_cbk(message))
    data = await state.get_data()
    await message.answer(f"Вот как будет выглядеть сообщение в рассылке:"
                         f"\n⬇️")
    await bot.copy_message(chat_id=message.from_user.id, from_chat_id=message.chat.id, message_id=data[
        "message"],
                           reply_markup=await get_callback_btns(btns=data["buttons"]))
    await message.answer("Приступим к рассылке?",
                         reply_markup=await get_callback_btns(btns={"Да": "confirm_mailing",
                                                                    "Переделать": "cancel_mailing"}))


@admin_private_router.callback_query(StateFilter(Mailing.message), F.data == "cancel_mailing")
@admin_private_router.callback_query(StateFilter(Mailing.buttons), F.data == "cancel_mailing")
async def cancel_mailing(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    current_state = await state.get_state()

    if current_state is not None:
        await state.set_state(Mailing.message)
        await callback.message.answer("Отправь сообщение, которое ты хочешь рассылать")


@admin_private_router.callback_query(StateFilter("*"), F.data == "confirm_mailing")
async def confirm_mailing(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    async with ChatActionSender.typing(bot=bot, chat_id=callback.message.from_user.id):
        await callback.answer("")
        await redis_set_mailing_users(await orm_get_mailing_list(session))
        data = await state.get_data()
        await redis_set_mailing_msg(str(data.get("message")))
        await redis_set_msg_from(str(callback.message.chat.id))
        await redis_set_mailing_btns(data.get("buttons"))
        await state.clear()

        success, notsuccess, blocked, elapsed_time_str = await simple_mailing()
        if elapsed_time_str == "":
            elapsed_time_str = "менее секунды"

        await callback.message.answer(
            text=f"Рассылка успешна.\n\nРезультаты:\nУспешно - {success}\nНеудачно - {notsuccess}\n\n"
                 f"Затрачено времени: <b>{elapsed_time_str}</b>\n\n"
                 f"<span class='tg-spoiler'>Бот заблокирован у {blocked} пользователя(ей)</span>",
            reply_markup=get_keyboard("Главное меню", "Сделать рассылку")
        )


# Mailing handlers ends


@admin_private_router.callback_query(F.data.startswith("required_status_"))
async def change_required_status(callback: CallbackQuery, session: AsyncSession):
    await callback.answer("")
    channel_id = int(callback.data.split("_")[-1])
    channel = await channel_info(channel_id=channel_id)
    required = await orm_is_required_channel(session, channel_id)
    print(type(required))
    print(required)

    text = f"Канал {channel.title} установлен {'' if required else 'не'}обязательным для " \
           f"постинга"
    await callback.message.answer(text=text,
                                  reply_markup=await get_callback_btns(btns={
                                      f"Изменить на {'не' if required else ''}обязательный":
                                          f"change_required_status_{channel_id}_{required}"
                                  }))


@admin_private_router.callback_query(F.data.startswith("change_required_status_"))
async def change_required_status(callback: CallbackQuery, session: AsyncSession):
    await callback.answer("")
    channel_id = int(callback.data.split("_")[-2])
    status = str(callback.data.split("_")[-1])
    print(type(status))
    print(status)
    channel = await channel_info(channel_id=channel_id)
    if status == "True":
        required = False
    else:
        required = True
    await orm_change_required_channel(session, channel_id, required)
    text = f"Канал {channel.title} установлен {'' if required else 'не'}обязательным для " \
           f"постинга"
    await callback.message.answer(text=text,
                                  reply_markup=await admin_kb()
                                  )


@admin_private_router.message(F.text == "Розыгрыши пользователей")
async def get_users_giveaways(message: Message, session: AsyncSession):
    users = await orm_get_users_with_giveaways(session)
    initial_text = "<b>👥Пользователи с розыгрышами</b>\n\n"
    text = initial_text
    messages = []
    limit = 4096

    for user in users:
        user_text = (f"/user_{user.user_id} <a href='tg://user?id={user.user_id}'"
                     f">{'@' + user.username if user.username else 'id' + str(user.user_id)}</a>\n")
        if len(text) + len(user_text) > limit:
            messages.append(text)
            text = initial_text + user_text
        else:
            text += user_text

    messages.append(text)

    for msg in messages:
        await message.answer(msg)


@admin_private_router.message(F.text.startswith("/user_"))
async def get_user_giveaways(message: Message, session: AsyncSession):
    user_id = int(message.text.split("_")[-1])
    user_givs = await format_giveaways_for_admin(await orm_get_user_giveaways(session=session, user_id=user_id))
    initial_text = f"<b>Розыгрыши <u><a href='tg://user?id={user_id}'>пользователя</a></u></b>\n\n"
    text = initial_text
    messages = []
    limit = 4096
    if not user_givs:
        await message.answer("❌ Пользователь не имеет розыгрышей!")
        return
    for giv in user_givs:
        giv_text = f"{giv}\n"
        if len(text) + len(giv_text) > limit:
            messages.append(text)
            text = initial_text + giv_text
        else:
            text += giv_text

    messages.append(text)
    for msg in messages:
        await message.answer(msg)


@admin_private_router.message(F.text.startswith("/usergive"))
async def get_user_giveaway(message: Message, session: AsyncSession):
    giveaway_id = int(message.text.split("/usergive")[1].strip())
    giveaway = await orm_get_giveaway_by_id(session=session, giveaway_id=giveaway_id)
    status = status_mapping.get(giveaway.status, "Неизвестный статус")
    post_url = giveaway.post_url
    participants_count = giveaway.participants_count if status == "Завершён" else await redis_get_participants_count(
        giveaway_id)
    winners_count = giveaway.winners_count
    end_count = giveaway.end_count
    end_datetime = giveaway.end_datetime.strftime('%d.%m.%Y %H:%M') if giveaway.end_datetime else None
    post_datetime = giveaway.post_datetime.strftime('%d.%m.%Y %H:%M')
    await message.answer("Вот как выглядит пост розыгрыша:")
    if status == "⏳ Ждёт публикации":
        await get_giveaway_post(giveaway, message.from_user.id)
    if status == "✅ Опубликован" or status == "❌ Завершён":
        await get_giveaway_post(giveaway, message.from_user.id)
    text = (f"<b>Розыгрыш №</b>{giveaway_id}\n"
            f"<b>Создатель розыгрыша:</b> {await get_user_creds(giveaway.user_id)}\n"
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


@admin_private_router.message(F.text == "Топ законченных розыгрышей")
async def get_top_finished_giveaways(message: Message, session: AsyncSession):
    top_finished_giveaways = await orm_get_top_giveaways_by_participants(session=session)
    if not top_finished_giveaways:
        await message.answer("❌ На данный момент нет законченных розыгрышей!")
        return
    initial_text = "<b>🏆Топ законченных розыгрышей</b>\n\n"
    text = initial_text
    messages = []
    limit = 4096
    places = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, giv in enumerate(top_finished_giveaways):
        giv_text = (f"{places[i]} /usergive{giv.id} <b>{giv.participants_count}</b>👥 | by: "
                    f"{await get_user_creds(giv.user_id)}\n")

        if len(text) + len(giv_text) > limit:
            messages.append(text)
            text = initial_text + giv_text
        else:
            text += giv_text

    messages.append(text)
    for msg in messages:
        await message.answer(msg)


# @admin_private_router.message(F.text == "Активные розыгрыши")
# async def get_active_giveaways(message: Message, session: AsyncSession):
#     active_giveaways = await orm_get_active_giveaways(session=session)
#     if not active_giveaways:
#         await message.answer("❌ На данный момент нет активных розыгрышей!")
#         return
#     text = format_giveaways(active_giveaways)
#     await message.answer(text)


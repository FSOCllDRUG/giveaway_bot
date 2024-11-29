from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.ext.asyncio import AsyncSession

from create_bot import bot
from db.pg_orm_query import orm_count_users, orm_get_mailing_list, orm_get_required_channels, orm_is_required_channel, \
    orm_change_required_channel
from db.r_operations import redis_set_mailing_users, redis_set_mailing_msg, redis_set_msg_from, redis_set_mailing_btns, \
    get_active_users_count
from filters.chat_type import ChatType
from filters.is_admin import IsAdmin
from keyboards.inline import get_callback_btns
from keyboards.reply import get_keyboard, admin_kb
from tools.mailing import simple_mailing
from tools.texts import cbk_msg
from tools.utils import msg_to_cbk, channel_info

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
            f"\n\n"
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
    await message.answer("Действие отменено", reply_markup=await admin_kb())


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
    await message.answer("Приступим к рассылке?", reply_markup=await get_callback_btns(btns={"Да": "confirm_mailing",
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


# @admin_private_router.message(F.text == "Список админов", IsOwner())
# async def add_admin_to_bot(message: Message, session: AsyncSession):
#     text: str = "Владелец бота:\n"
#     owner: int = env_admins[1]
#     id_for_query = int(owner)
#     user = await orm_get_user_data(session, id_for_query)
#     user_link = f"<a href='tg://user?id={user.user_id}'>{user.user_id}</a>"
#     text += (
#         f"👤 Телеграм ID: {user_link}\n"
#         f"📝 Полное имя: {user.name}\n"
#     )
#
#     if user.username is not None:
#         text += f"🔑 Логин: @{user.username}\n"
#
#     if message.from_user.id in env_admins:
#         text += await admins_list_text(session)
#         admins = await orm_get_admins(session)
#         for admin in admins:
#             channels = await orm_get_channels_for_admin(session, admin.user_id)
#             if channels:
#                 channels_str = ""
#                 for channel in channels:
#                     chat = await bot.get_chat(channel.channel_id)
#                     channels_str += f"<a href='{chat.invite_link}'>{chat.title}</a>\n"
#                 text += f"Каналы:\n{channels_str}"
#             else:
#                 text += "Не подключен к каналам\n"
#     await message.answer(text=text,
#                          reply_markup=await get_callback_btns(btns={"Добавить админа": "add_admin",
#                                                               "Удалить админа": "del_admin",
#                                                               "Стукнуть разраба": link_to_dev},
#                                                         sizes=(1,)))


# @admin_private_router.callback_query(F.data == "del_admin")
# async def del_admin(callback: CallbackQuery, session: AsyncSession):
#     await callback.answer("")
#     admins = await orm_get_admins(session)
#     btns = {}
#     for admin in admins:
#         btns[f"{admin.name} ({admin.user_id})"] = f"delete_admin_{admin.user_id}"
#     await callback.message.answer("Добавленные администраторы:",
#                                   reply_markup=await get_callback_btns(btns=btns, sizes=(1,)))


# @admin_private_router.callback_query(F.data.startswith("delete_admin_"))
# async def delete_admin(callback: CallbackQuery, session: AsyncSession):
#     admin_id = int(callback.data.split("_")[-1])
#     await orm_delete_admin(session, admin_id)
#     await update_admins(session, env_admins)
#     admins = await orm_get_admins(session)
#     btns = {}
#     for admin in admins:
#         btns[f"{admin.name} ({admin.user_id})"] = f"delete_admin_{admin.user_id}"
#     await callback.message.edit_text("Администратор успешно удалён!")


# class AddAdmin(StatesGroup):
#     user_id = State()
#     confirm = State()


# @admin_private_router.callback_query(F.data == "add_admin")
# async def add_admin(callback: CallbackQuery, state: FSMContext):
#     await callback.answer("")
#     await state.set_state(AddAdmin.user_id)
#     await callback.message.answer("Перешли сообщение от юзера, которого хочешь сделать админом\n\n"
#                                   "‼️<b><u>ВАЖНО</u></b>‼️\n"
#                                   "Это должен быть пользователь, который взаимодействовал с ботом",
#                                   reply_markup=get_keyboard("Отмена"))


# @admin_private_router.message(AddAdmin.user_id)
# async def get_admin_id(message: Message, state: FSMContext, session: AsyncSession):
#     try:
#         text = "Ты хочешь сделать администратором пользователя:\n\n"
#         user_id = await get_chat_id(message)
#         await state.update_data(user_id=user_id)
#         user = await orm_get_user_data(session, user_id)
#         if user is None:
#             await message.answer("Пользователь ещё не запускал бота!")
#             return
#         elif await redis_check_admin(user_id):
#             await message.answer("Пользователь уже админ!\n"
#                                  "Возвращаю тебя в админ панель", reply_markup=admin_kb())
#             await state.clear()
#             return
#         user_link = f"<a href='tg://user?id={user.user_id}'>{user.user_id}</a>"
#         text += (
#             f"👤 Телеграм ID: {user_link}\n"
#             f"📝 Полное имя: {user.name}\n"
#         )
#
#         if user.username is not None:
#             text += f"🔑 Логин: @{user.username}\n"
#         await message.answer(text=text,
#                              reply_markup=await get_callback_btns(btns={"Подтвердить":
#                                                                       "confirm"}))
#         await state.set_state(AddAdmin.confirm)
#     except ValueError:
#         await message.answer("Некорректный ID админа, попробуй снова!")


# @admin_private_router.callback_query(F.data == "confirm", StateFilter(AddAdmin.confirm))
# async def add_admin_done(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
#     await callback.answer("")
#     data = await state.get_data()
#     admin_id = data.get("user_id")
#     await orm_add_admin(session, admin_id)
#     text = "Администратор добавлен в базу данных!"
#     text += await admins_list_text(session)
#     await callback.message.answer(text=text, reply_markup=admin_kb())
#     await update_admins(session, env_admins)
#     await state.clear()


@admin_private_router.callback_query(F.data.startswith("required_status_"))
async def change_required_status(callback: CallbackQuery, session: AsyncSession):
    await callback.answer("")
    channel_id = int(callback.data.split("_")[-1])
    channel = await channel_info(channel_id)
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
    channel = await channel_info(channel_id)
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

# class AddAdminChannel(StatesGroup):
#     channel_id = State()
#     confirm = State()
#
#
# @admin_private_router.callback_query(F.data.startswith("add_admin_to_channel_"))
# async def add_admin_to_channel(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
#     channel_id = int(callback.data.split("_")[-1])
#     await callback.answer("")
#     await state.update_data(channel_id=channel_id)
#     admins = await orm_get_admins(session)
#     channel_admins = await orm_get_admins_in_channel(session, channel_id)
#     channel_admins_ids = [admin.user_id for admin in channel_admins]
#     available_admins = [admin for admin in admins if admin.user_id not in channel_admins_ids]
#     if not available_admins:
#         await callback.message.answer("Нет доступных администраторов для добавления в канал.")
#         return
#     btns = {}
#     for admin in available_admins:
#         btns[f"{admin.name} ({admin.user_id})"] = f"add_admin_{admin.user_id}"
#     await callback.message.answer("Выберите админа, которого вы хотите добавить к выбранному каналу из списка:",
#                                   reply_markup=await get_callback_btns(btns=btns, sizes=(1,)))
#     await state.set_state(AddAdminChannel.confirm)
#
#
# @admin_private_router.callback_query(F.data.startswith("add_admin_"), StateFilter(AddAdminChannel.confirm))
# async def confirm_add_admin_to_channel(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
#     admin_id = int(callback.data.split("_")[-1])
#     data = await state.get_data()
#     channel_id = data.get("channel_id")
#     await orm_add_admin_to_channel(session, admin_id, channel_id)
#     await callback.message.answer("Администратор добавлен в канал!")
#     await state.clear()

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.ext.asyncio import AsyncSession

from create_bot import bot
from db.pg_orm_query import orm_get_required_channels, orm_delete_channel, orm_add_channel, \
    orm_add_admin_to_channel
from db.pg_orm_query import (
    orm_user_start,
    orm_get_user_data,
    orm_get_channels_for_admin)
from db.r_operations import redis_check_channel, redis_get_channel_id
from filters.chat_type import ChatType
from keyboards.inline import get_callback_btns
from keyboards.reply import main_kb, get_keyboard
from middlewares.activity_middleware import ActivityMiddleware
from tools.texts import cbk_msg
from tools.utils import msg_to_cbk, channel_info, convert_id, is_subscribed, get_channel_hyperlink, is_admin

user_router = Router()
user_router.message.middleware(ActivityMiddleware())
user_router.message.filter(ChatType("private"))


@user_router.message(StateFilter("*"), F.text == "/cancel")
@user_router.message(StateFilter("*"), F.text.casefold() == "отмена")
async def cancel_fsm(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Действие отменено.",
                         reply_markup=await main_kb(await is_admin(message.from_user.id)))


@user_router.callback_query(StateFilter("*"), F.data == "cancel")
async def cancel_fsm(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("")
    await callback.message.answer("❌ Действие отменено.",
                                  reply_markup=await main_kb(await is_admin(callback.from_user.id)))


# "/start" handler
@user_router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    text = ("Добро пожаловать в <b>WinGiveBot</b>!\n\n"
            "Бот способен организовывать розыгрыши для участников одного или нескольких <b>telegram-каналов</b> и "
            "автоматически определять победителей в установленное время.\n\n"
            "❗️Также в Нашем боте присутствует <b>капча</b> для защиты от накрутки ботов.\n"
            "И самое интересное, у нас есть функция создания постов с кнопкой!"
            )
    if await orm_get_user_data(session, user_id=message.from_user.id) is not None:
        await message.answer(text,
                             reply_markup=await main_kb(await is_admin(message.from_user.id)))
    else:
        await orm_user_start(session, data={
            "user_id": message.from_user.id,
            "username": message.from_user.username if message.from_user.username is not None else None,
            "name": message.from_user.full_name,
        })
        await message.answer(text,
                             reply_markup=await main_kb(await is_admin(message.from_user.id)))


@user_router.message(F.text == "Главное меню")
async def main_menu(message: Message):
    await message.answer("<b>Вы в главном меню!</b>", reply_markup=await main_kb(await is_admin(
        message.from_user.id)))


@user_router.message(Command("my_channels"))
@user_router.message(F.text == "Мои каналы/чаты")
async def get_user_channels(message: Message, session: AsyncSession):
    user_id = message.from_user.id
    channels = await orm_get_channels_for_admin(session, user_id)
    if not channels:
        await message.answer("У тебя нет каналов/групп 🫥",
                             reply_markup=await get_callback_btns(btns={"Добавить канал/группу": "add_channel"}))
        return
    channels_str = ""
    btns = {}
    for channel in channels:
        chat = await channel_info(channel.channel_id)
        if chat is None:
            await message.answer("Ошибка в канале с id: " + str(channel.channel_id))
        channels_str += f"{await get_channel_hyperlink(channel.channel_id)}\n"
        btns[chat.title] = f"channel_{channel.channel_id}"
    btns["Добавить канал/группу"] = "add_channel"
    await message.answer(f"❗️<b>Ваши каналы:</b>\n{channels_str}",
                         reply_markup=await get_callback_btns(btns=btns, sizes=(1,)))


class AddChannel(StatesGroup):
    admin_id = State()
    channel_id = State()
    approve = State()


@user_router.callback_query(F.data == "add_channel")
async def start_add_channel(callback: CallbackQuery, state: FSMContext):
    await state.update_data(admin_id=callback.from_user.id)
    await callback.answer("")
    await callback.message.answer("Добавь меня в <b>свой</b> канал\n"
                                  "в роли администратора!\n\n"
                                  "Необходимые права для работы бота:\n"
                                  "\n✅ Отправка сообщений"
                                  "\n✅ Удаление сообщений"
                                  "\n✅ Редактирование сообщений\n\n"
                                  "<b>После того как добавишь меня в канал, нажми на кнопку</b>⬇️",
                                  reply_markup=await get_callback_btns(btns={"Я добавил бота!": "added_to_channel"}))
    await state.set_state(AddChannel.channel_id)


@user_router.callback_query(StateFilter(AddChannel.channel_id), F.data == "added_to_channel")
async def bot_added_to_channel(callback: CallbackQuery, state: FSMContext):
    chat_id = await redis_get_channel_id(callback.from_user.id)
    if chat_id is None:
        await callback.answer("")
        await callback.message.answer("Ты меня ещё никуда не добавил!")
        return
    else:
        await callback.answer("")
        await state.update_data(channel_id=chat_id)
        await callback.message.answer(f"Это этот канал/группа:"
                                      f"\n•{await get_channel_hyperlink(chat_id)}?",
                                      reply_markup=await get_callback_btns(btns={"Да": "yes", "Отмена": "cancel"}))
        await state.set_state(AddChannel.approve)


@user_router.callback_query(StateFilter(AddChannel.approve), F.data == "yes")
async def check_channel(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer("")
    data = await state.get_data()
    channel_id = data.get("channel_id")
    user_id = data.get("admin_id")
    if channel_id:
        check = await redis_check_channel(user_id, channel_id)
        if check:
            await orm_add_channel(session, channel_id)
            await orm_add_admin_to_channel(session, user_id, channel_id)
            await callback.message.answer(
                "✅ <b>Канал/группа</b>\n"
                "<b>добавлен(а) успешно!</b>\n\n"
                "Чтобы создать новый розыгрыш введите команду /new_give",
                reply_markup=await main_kb(await is_admin(callback.from_user.id)))
            await state.clear()

        else:
            await callback.message.answer("Либо ты меня ещё не добавил в канал, либо что-то пошло не так :(")
    else:
        await callback.message.answer("Я не смог разобрать твоё сообщение, пожалуйста, следуй условиям описанным выше!")


@user_router.callback_query(F.data.startswith("channel_"))
async def channel_chosen(callback: CallbackQuery):
    channel_id = int(callback.data.split("_")[-1])
    channel = await channel_info(channel_id)
    btns = {
        "Создать пост": f"create_post_{channel_id}",
        "Удалить из бота": f"delete_channel_{channel_id}",
    }
    if await is_admin(callback.from_user.id):
        btns["Изменить статус"] = f"required_status_{channel_id}"
    await callback.answer("")
    await callback.message.answer(
        f"Выберите действие для {channel.title}:\n",
        reply_markup=await get_callback_btns(
            btns=btns, sizes=(1,)
        )
    )


@user_router.callback_query(F.data.startswith("delete_channel_"))
async def delete_channel(callback: CallbackQuery, session: AsyncSession):
    await callback.answer("")
    channel_id = int(callback.data.split("_")[-1])
    await orm_delete_channel(session, channel_id)
    await callback.message.answer("✅ <b>Канал успешно удален!</b>",
                                  reply_markup=await main_kb(await is_admin(callback.from_user.id)))


@user_router.message(F.text == "Создать пост")
async def create_post(message: Message, session: AsyncSession):
    if await is_subscribed(channels=await orm_get_required_channels(session), user_id=message.from_user.id):
        user_id = message.from_user.id
        channels = await orm_get_channels_for_admin(session, user_id)
        if not channels:
            await message.answer("У тебя нет каналов/групп 🫥",
                                 reply_markup=await get_callback_btns(btns={"Добавить канал/группу": "add_channel"}))
            return
        channels_str = ""
        btns = {}
        for channel in channels:
            chat = await channel_info(channel.channel_id)
            channels_str += f"{await get_channel_hyperlink(channel.channel_id)}\n"
            btns[chat.title] = f"create_post_{channel.channel_id}"
        btns["Добавить канал/группу"] = "add_channel"
        await message.answer("<b>В какой канал делаем пост?</b>\n"
                             "📊Ваши каналы:",
                             reply_markup=await get_callback_btns(btns=btns, sizes=(1,)))
    else:
        btns = {}
        required_channels = await orm_get_required_channels(session)
        for channel in required_channels:
            chat = await bot.get_chat(channel.channel_id)
            chat_invite_link = chat.invite_link
            btns[chat.title] = f"{chat_invite_link}"

        await message.answer("Для доступа к функции <b>«posting»</b> необходимо быть подписчиком канала(ов) ниже.\n\n"
                             "❗️<b>После подписки нажмите</b>\n"
                             "<b>снова на кнопку «Создать пост»</b>",
                             reply_markup=await get_callback_btns(btns=btns, sizes=(1,)))


class CreatePost(StatesGroup):
    channel_id = State()
    message = State()
    buttons = State()


# Channel post handlers starts
@user_router.callback_query(StateFilter(None), F.data.startswith("create_post_"))
async def make_post(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    required_channels = await orm_get_required_channels(session)
    if await is_subscribed(channels=required_channels, user_id=callback.from_user.id):
        await state.set_state(CreatePost.channel_id)
        await callback.answer("")
        channel_id = int(callback.data.split("_")[-1])
        await state.update_data(channel_id=channel_id)
        await callback.message.answer("Отправь сообщение, которое будем постить\n\n"
                                      "<b>❗️ВАЖНО.</b>\n\n"
                                      "В посте может быть\n"
                                      "приложен только <b><u>один</u></b> файл!\n\n"
                                      "<i>Файл - фото/видео/документ</i>\n"
                                      "<i>голосовое сообщение/видео сообщение!</i>",
                                      reply_markup=get_keyboard("Отмена",
                                                                placeholder="Отправь сообщение, для поста"
                                                                )
                                      )
        await state.set_state(CreatePost.message)
    else:
        await callback.answer("")
        btns = {}
        required_channels = await orm_get_required_channels(session)
        for channel in required_channels:
            chat = await bot.get_chat(channel.channel_id)
            chat_invite_link = chat.invite_link
            btns[chat.title] = f"{chat_invite_link}"

        await callback.message.answer(
            "Для доступа к функции <b>«posting»</b> необходимо быть подписчиком канала(ов) ниже.\n\n"
            "❗️<b>После подписки нажмите</b>\n"
            "<b>снова на кнопку «Создать пост»</b>",
            reply_markup=await get_callback_btns(btns=btns, sizes=(1,)))
        await state.clear()


@user_router.message(StateFilter(CreatePost.message))
async def get_message_for_post(message: Message, state: FSMContext):
    await state.update_data(message=message.message_id)
    await state.set_state(CreatePost.buttons)
    await message.reply("Будем добавлять URL-кнопки к посту?", reply_markup=await get_callback_btns(
        btns={"Да": "add_btns",
              "Пост без кнопок": "confirm_post", "Переделать": "cancel_post"}
    )
                        )


@user_router.callback_query(StateFilter(CreatePost.buttons), F.data == "add_btns")
async def add_btns_post(callback: CallbackQuery):
    await callback.answer("")
    await callback.message.answer(cbk_msg)


@user_router.message(StateFilter(CreatePost.buttons), F.text.contains(":"))
async def btns_to_data(message: Message, state: FSMContext):
    await state.update_data(buttons=await msg_to_cbk(message))
    data = await state.get_data()
    await message.answer(f"Вот как будет выглядеть пост в канале:")
    await bot.copy_message(chat_id=message.from_user.id, from_chat_id=message.chat.id, message_id=data[
        "message"],
                           reply_markup=await get_callback_btns(btns=data["buttons"]))
    await message.answer("Приступим к постингу?",
                         reply_markup=await get_callback_btns(btns={"Да": "confirm_post",
                                                                    "Переделать": "cancel_post"}))


@user_router.callback_query(StateFilter(CreatePost.message), F.data == "cancel_post")
@user_router.callback_query(StateFilter(CreatePost.buttons), F.data == "cancel_post")
async def cancel_mailing(callback: CallbackQuery, state: FSMContext):
    await callback.answer("")
    current_state = await state.get_state()

    if current_state is not None:
        await state.set_state(CreatePost.message)
        await callback.message.answer("Отправь сообщение, которое будем постить")


@user_router.callback_query(StateFilter("*"), F.data == "confirm_post")
async def confirm_post(callback: CallbackQuery, state: FSMContext):
    async with ChatActionSender.typing(bot=bot, chat_id=callback.message.from_user.id):
        await callback.answer("")
        data = await state.get_data()
        if "buttons" not in data:
            post_id = await bot.copy_message(chat_id=data["channel_id"], from_chat_id=callback.message.chat.id,
                                             message_id=data["message"])
        else:
            post_id = await bot.copy_message(chat_id=data["channel_id"], from_chat_id=callback.message.chat.id,
                                             message_id=data["message"],
                                             reply_markup=await get_callback_btns(btns=data["buttons"]))

        await callback.message.answer("✅ <b>Пост успешно создан!</b>\n"
                                      f"Ссылка на пост: https://t.me/c/{await convert_id(data['channel_id'])}"
                                      f"/{post_id.message_id}",
                                      reply_markup=await main_kb(await is_admin(callback.from_user.id)))

        await state.clear()


@user_router.message(F.text == "Поддержка")
async def support(message: Message):
    await message.answer("💬<b>Служба поддержки:</b>\n"
                         "https://t.me/mrktmng\n\n"

                         "<b>🗒️Инструкция по</b>\n"
                         "<b>использованию бота:</b>\n"
                         "https://t.me/WinGiveInfo\n\n"

                         "Если Вы сделаете все по инструкции,то у Вас все получится!")


@user_router.message(Command("developer"))
async def developer(message: Message):
    await message.answer(f"Контакты разработчика:\n"
                         f"Telegram: <b><i><u><a href='tg://user?id=6092344340'>*НАПИСАТЬ*</a></u></i></b>\n"
                         f"Email: fsoclldrug@gmail.com")

# @user_router.message(F.photo)
# async def get_photo_id(message: Message):
#     photo_id = message.photo[-1].file_id
#     await message.answer(f"id фотографии:\n<pre>{photo_id}</pre>")

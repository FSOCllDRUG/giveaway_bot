import asyncio

from aiogram.types import BotCommand, BotCommandScopeDefault

from create_bot import bot, dp, env_admins
from db.pg_engine import create_db
from db.pg_engine import session_maker
from handlers.admin_private import admin_private_router
from handlers.channels import channel_router
from handlers.groups import group_router
from handlers.user_router import user_router
from middlewares.db import DbSessionMiddleware


async def set_commands():
    commands = [BotCommand(command="start", description="Старт"),
                BotCommand(command="profile", description="Мой профиль")]
    await bot.set_my_commands(commands, BotCommandScopeDefault())


async def start_bot():
    await set_commands()
    admins = env_admins
    try:
        for admin_id in admins:
            await bot.send_message(admin_id, f"Бот запущен🥳.{admins}")
    except:
        pass


async def stop_bot():
    try:
        for admin_id in env_admins:
            await bot.send_message(admin_id, "Бот остановлен.\n😴")
    except:
        pass



async def main():
    await create_db()
    dp.include_router(user_router)
    dp.include_router(admin_private_router)
    dp.include_router(channel_router)
    dp.include_router(group_router)
    dp.update.middleware(DbSessionMiddleware(session_pool=session_maker))

    dp.startup.register(start_bot)
    dp.shutdown.register(stop_bot)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from decouple import config

from loggers.setup_logger import module_logger

env_admins = [int(admin_id) for admin_id in config("ADMINS").split(",")]

module_logger("aiogram", "logs_bot", "bot.log", logging.ERROR, console=True)
module_logger("sqlalchemy", "logs_db", "db.log", logging.ERROR)
bot = Bot(token=config("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML,
                                                                  link_preview_is_disabled=True))
redis_storage = RedisStorage.from_url(config("REDIS_URL"))
dp = Dispatcher(storage=redis_storage)

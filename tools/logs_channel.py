import asyncio

from decouple import config

from create_bot import bot

logs_channel_id = int(config("LOGS_CHANNEL_ID"))


async def send_log(text: str):
    await asyncio.sleep(1 / 20)
    await bot.send_message(chat_id=logs_channel_id, text=text)

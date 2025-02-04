import base64
import datetime
import re
from types import NoneType

import pytz

from db.pg_models import GiveawayStatus


async def datetime_example():
    now = datetime.datetime.now(pytz.timezone("Europe/Moscow"))
    text = ("<b>ПРИМЕРЫ:</b>\n"
            f"<code>{(now + datetime.timedelta(minutes=10)).strftime('%d.%m.%Y %H:%M')}</code> - через 10 минут\n"
            f"<code>{(now + datetime.timedelta(hours=1)).strftime('%d.%m.%Y %H:%M')}</code> - через час\n"
            f"<code>{(now + datetime.timedelta(days=1)).strftime('%d.%m.%Y %H:%M')}</code> - через день\n"
            f"<code>{(now + datetime.timedelta(days=7)).strftime('%d.%m.%Y %H:%M')}</code> - через неделю")
    return text


async def encode_giveaway_id(giveaway_id: int) -> str:
    return base64.urlsafe_b64encode(str(giveaway_id).encode()).decode()


async def decode_giveaway_id(encoded_id: str) -> int:
    return int(base64.urlsafe_b64decode(encoded_id.encode()).decode())


cbk_msg = ("<b>Отправь содержание кнопок вида:</b>\n\n"
           "текст кнопки:ссылка\n"
           "текст кнопки:ссылка\n\n"
           "Пример: \n<pre>Перейти на сайт:https://example.com\n"
           "Перейти к посту:https://t.me/for_test_ch/3</pre>"
           "\n\n"
           "❗️<b>Количество кнопок должно быть не более 10 штук.</b>\n\n"
           "Кнопки присылать <b><u>ОДНИМ</u></b> сообщением, каждая кнопка должна быть с новой строки, как указано в "
           "примере!")

captcha_on_text = ("❗️<b>ВНИМАНИЕ.</b>\n"
                   "✅ <i>Вы включили капчу!</i>\n\n"

                   "<b>Теперь каждый пользователь перед участием должен будет решить графическую капчу</b>❗️\n\n"

                   "При нажатии на кнопку участия, пользователю будет предложено ввести в Нашем боте цифры, "
                   "которые будут на картинке.\n\n"

                   "⚠️<b>Эта функция создана для того, чтобы в конкурсе невозможно было </b>"
                   "<b>накрутить ботов.</b>")

captcha_off_text = ("ℹ️ <i>Вы отключили капчу</i>❌\n"
                    "Теперь для участия в розыгрыше участникам не нужно решать графическую капчу.")


async def remove_html_tags(text):
    # Remove HTML tags and unfinished HTML tags
    clean_text = re.sub(r"<.*?>|<.*", "", text)
    # Replace newlines and other whitespace characters with a single space
    clean_text = re.sub(r"\s+", " ", clean_text)
    return clean_text


async def format_giveaways(giveaways):
    formatted_giveaways = []
    for giveaway in giveaways:
        giveaway_id, text, status = giveaway
        clean_text = await remove_html_tags(text)
        status_icon = {
            GiveawayStatus.NOT_PUBLISHED: "⏳",
            GiveawayStatus.PUBLISHED: "✅",
            GiveawayStatus.FINISHED: "☑️"
        }.get(status, "❓")
        formatted_giveaways.append(f"{status_icon} /mygive{giveaway_id} {clean_text}")
    return formatted_giveaways


async def format_giveaways_for_admin(giveaways):
    formatted_giveaways = []
    for giveaway in giveaways:
        giveaway_id, text, status = giveaway
        clean_text = await remove_html_tags(text)
        status_icon = {
            GiveawayStatus.NOT_PUBLISHED: "⏳",
            GiveawayStatus.PUBLISHED: "✅",
            GiveawayStatus.FINISHED: "☑️"
        }.get(status, "❓")
        formatted_giveaways.append(f"{status_icon} /usergive{giveaway_id} {clean_text}")
    return formatted_giveaways


async def channel_conditions_text(channel) -> str:
    if channel is not None:
        text = f"✅ Подпишись на <a href='{channel.invite_link}'>{channel.title}</a>\n"
    else:
        text = f"✅ Подпишись на (бота удалили из канала)\n"
    return text

import base64
import datetime
import re

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


async def remove_html_tags(text):
    clean_text = re.sub(r"<.*?>", "", text)
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
           "❗️<b>Количество кнопок</b>\n"
           "<b>должно быть не более 10.</b>"
           "Кнопки присылать <b><u>ОДНИМ</u></b> сообщением, каждая кнопка\n"
           "с новой строки!")

captcha_on_text = ("❗️<b>ВНИМАНИЕ.</b>\n"
                   "✅ <i>Вы включили капчу!</i>\n\n"

                   "<b>Теперь каждый пользователь перед участием должен будет решить графическую капчу</b>❗️"

                   "При нажатии на кнопку участия, пользователю будет предложено ввести в Нашем боте цифры, "
                   "которые будут на картинке.\n\n"

                   "⚠️<b>Эта функция создана для того, чтобы в конкурсе невозможно было</b>"
                   "<b>накрутить ботов.</b>")

captcha_off_text = ("ℹ️ <i>Вы отключили капчу</i>❌\n"
                    "Теперь для участия в розыгрыше участникам не нужно решать графическую капчу.")

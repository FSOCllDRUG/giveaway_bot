from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


async def get_callback_btns(
        *,
        btns: dict[str, str],
        sizes: tuple[int] = (2,)):
    keyboard = InlineKeyboardBuilder()

    for text, value in btns.items():
        if "://" in value:
            keyboard.add(InlineKeyboardButton(text=text, url=value))
        else:
            keyboard.add(InlineKeyboardButton(text=text, callback_data=value))

    return keyboard.adjust(*sizes).as_markup()


def change_mailing_buttons(user_id, mailing_status):
    if mailing_status:
        buttons = {
            "Отписаться от рассылки": f"change_mailing_{user_id}_0",
        }
    else:
        buttons = {
            "Подписаться на рассылку": f"change_mailing_{user_id}_1",
        }
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn_text, callback_data=callback_data) for btn_text, callback_data in
         buttons.items()]
    ])

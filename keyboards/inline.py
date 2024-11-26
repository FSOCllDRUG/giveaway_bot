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


async def captcha_toggle(change_to: str):
    if change_to == "on":
        buttons = {
            "✅Использовать капчу": "captcha_off",
            "Сохранить розыгрыш": "save_giveaway",
            "Отмена": "cancel"
        }
    else:
        buttons = {
            "❌Использовать капчу": "captcha_on",
            "Сохранить розыгрыш": "save_giveaway",
            "Отмена": "cancel"
        }
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn_text, callback_data=callback_data)]
        for btn_text, callback_data in buttons.items()
    ])

from aiogram import Router, F
from aiogram.types import Message

from keyboards.business import business_menu
from keyboards.main import main_menu

router = Router()


@router.message(F.text == "💼 Бизнес")
async def business_menu_handler(message: Message):
    await message.answer(
        "💼 <b>Раздел бизнеса</b>\n\n"
        "Выберите инструмент:",
        parse_mode="HTML",
        reply_markup=business_menu
    )


@router.message(F.text == "⬅️ Назад")
async def back_to_main(message: Message):
    await message.answer(
        "🏠 Главное меню",
        reply_markup=main_menu
    )
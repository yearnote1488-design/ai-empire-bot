from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from keyboards.main import main_menu
from database.db import add_user

router = Router()


@router.message(CommandStart())
async def start(message: Message):
    await add_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )

    text = (
        "👑 <b>AI Империя</b>\n\n"
        "Добро пожаловать!\n\n"
        "Я — ваш персональный AI-директор.\n\n"
        "🚀 Помогу запустить бизнес\n"
        "📈 Увеличить прибыль\n"
        "💼 Найти новые идеи\n"
        "📊 Проанализировать конкурентов\n"
        "✍️ Создать маркетинговую стратегию\n\n"
        "👇 Выберите раздел в меню."
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=main_menu
    )
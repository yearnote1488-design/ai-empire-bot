from aiogram import Router, F
from aiogram.types import Message

from database.db import get_user

router = Router()


@router.message(F.text == "👤 Кабинет")
async def profile(message: Message):
    user = await get_user(message.from_user.id)

    if not user:
        await message.answer("Пользователь не найден.")
        return

    first_name, username, requests, plan = user

    text = f"""
👤 <b>Личный кабинет</b>

🪪 Имя: {first_name}

📛 Username: @{username if username else "не указан"}

📊 Запросов: {requests}

💎 Тариф: {plan}
"""

    await message.answer(
        text,
        parse_mode="HTML"
    )
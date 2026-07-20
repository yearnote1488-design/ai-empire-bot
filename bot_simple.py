import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / '.env')

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ⚠️ ЗАМЕНИ НА СВОЙ ID
ADMIN_ID = 271725844

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("✅ Бот работает! Напиши /admin")

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Тест", callback_data="admin_test")]
    ])
    await message.answer("👑 Админ-панель работает!", reply_markup=kb)

@dp.callback_query(F.data == "admin_test")
async def admin_test(callback: CallbackQuery):
    await callback.message.edit_text("✅ Кнопка работает!")
    await callback.answer()

async def main():
    print("🚀 Тестовый бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
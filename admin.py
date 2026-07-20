import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db

router = Router()

# ===== СОСТОЯНИЕ ДЛЯ РАССЫЛКИ =====
class BroadcastState(StatesGroup):
    waiting_for_text = State()

# ===== АДМИН-ПАНЕЛЬ =====

@router.message(Command("admin"))
async def admin_panel(message: Message):
    """Вход в админ-панель"""
    # ⚠️ ЗАМЕНИ НА СВОЙ ID (узнай через @userinfobot)
    ADMIN_ID = 8965659253
    
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен.")
        return

    stats = db.get_stats()

    text = (
        "👑 *Админ-панель AI Империя*\n\n"
        f"📊 *Статистика:*\n"
        f"• 👥 Всего пользователей: {stats['total_users']}\n"
        f"• 💎 Премиум: {stats['premium_users']}\n"
        f"• 📝 Всего запросов: {stats['total_requests']}\n"
        f"• 💰 Доход: {stats['revenue']} ⭐\n\n"
        "Выберите действие:"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список пользователей", callback_data="admin_users")],
        [InlineKeyboardButton(text="⭐ Модерация отзывов", callback_data="admin_reviews")],
        [InlineKeyboardButton(text="📨 Массовая рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="⬅️ Выйти", callback_data="admin_exit")]
    ])

    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_"))
async def admin_actions(callback: CallbackQuery, state: FSMContext):
    ADMIN_ID = 8965659253
    
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен.")
        return

    action = callback.data.replace("admin_", "")

    if action == "users":
        users = db.get_all_users()
        if not users:
            await callback.message.edit_text("📋 *Список пользователей*\n\nПользователей пока нет.", parse_mode="Markdown")
            await callback.answer()
            return

        text = "📋 *Список пользователей*\n\n"
        for i, user in enumerate(users[:10], 1):
            status = "💎" if user[2] == 'premium' else "🆓"
            text += f"{i}. {status} {user[1]} (ID: {user[0]}) | {user[3]} запросов\n"

        if len(users) > 10:
            text += f"\n... и еще {len(users) - 10} пользователей"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()

    elif action == "reviews":
        reviews = db.get_unapproved_reviews()
        if not reviews:
            await callback.message.edit_text(
                "⭐ *Модерация отзывов*\n\nВсе отзывы одобрены. Отличная работа! 🎉",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")]
                ]),
                parse_mode="Markdown"
            )
            await callback.answer()
            return

        text = "⭐ *Модерация отзывов*\n\n"
        for review in reviews[:5]:
            stars = "⭐" * review[3]
            text += f"📝 *{review[1]}* ({stars})\n"
            text += f"📄 {review[2][:200]}{'...' if len(review[2]) > 200 else ''}\n"
            text += f"🆔 ID: {review[0]}\n\n"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить все", callback_data="admin_approve_all")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()

    elif action == "approve_all":
        reviews = db.get_unapproved_reviews()
        for review in reviews:
            db.approve_review(review[0])
        await callback.message.edit_text(
            "✅ Все отзывы одобрены!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")]
            ]),
            parse_mode="Markdown"
        )
        await callback.answer()

    elif action == "broadcast":
        await state.set_state(BroadcastState.waiting_for_text)
        await callback.message.edit_text(
            "📨 *Массовая рассылка*\n\n"
            "Отправьте текст сообщения, которое хотите разослать всем пользователям.\n\n"
            "Для отмены напишите /cancel",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin_back")]
            ]),
            parse_mode="Markdown"
        )
        await callback.answer()

    elif action == "exit":
        await callback.message.edit_text("👑 *Выход из админ-панели*", parse_mode="Markdown")
        await callback.answer()

    elif action == "back":
        stats = db.get_stats()
        text = (
            "👑 *Админ-панель AI Империя*\n\n"
            f"📊 *Статистика:*\n"
            f"• 👥 Всего пользователей: {stats['total_users']}\n"
            f"• 💎 Премиум: {stats['premium_users']}\n"
            f"• 📝 Всего запросов: {stats['total_requests']}\n"
            f"• 💰 Доход: {stats['revenue']} ⭐\n\n"
            "Выберите действие:"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список пользователей", callback_data="admin_users")],
            [InlineKeyboardButton(text="⭐ Модерация отзывов", callback_data="admin_reviews")],
            [InlineKeyboardButton(text="📨 Массовая рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="⬅️ Выйти", callback_data="admin_exit")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()

@router.message(BroadcastState.waiting_for_text, F.text)
async def broadcast_send(message: Message, state: FSMContext):
    ADMIN_ID = 8965659253
    
    if message.from_user.id != ADMIN_ID:
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Рассылка отменена.")
        return

    await message.answer("📨 Начинаю рассылку... Это может занять время.")

    users = db.get_all_users()
    success = 0
    failed = 0

    for user in users:
        try:
            await message.bot.send_message(
                user[0],
                message.text,
                parse_mode="Markdown"
            )
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await state.clear()
    await message.answer(
        f"✅ *Рассылка завершена!*\n\n"
        f"• 📤 Отправлено: {success}\n"
        f"• ❌ Не доставлено: {failed}\n"
        f"• 👥 Всего пользователей: {len(users)}",
        parse_mode="Markdown"
    )
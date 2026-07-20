import asyncio
import os
import logging
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery, SuccessfulPayment
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from ai.chat import AIChat
from database import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PREMIUM_PRODUCT_ID = os.getenv("PREMIUM_PRODUCT_ID")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env файле!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

ai_assistant = AIChat()

# ===== ID АДМИНИСТРАТОРА =====
ADMIN_ID = 271725844

# ===== СОСТОЯНИЯ =====
class Form(StatesGroup):
    waiting_for_question = State()
    waiting_for_document = State()
    waiting_for_idea_topic = State()
    waiting_for_review = State()

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def clean_markdown(text: str) -> str:
    text = re.sub(r'\*\*\s*\*\*', '', text)
    text = re.sub(r'__\s*__', '', text)
    text = re.sub(r'~~\s*~~', '', text)
    text = re.sub(r'\*\*[\s\n]+\*\*', '', text)
    text = re.sub(r'\*\*\*+', '**', text)
    text = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', text)
    return text.strip()

async def safe_send_message(message: Message, text: str, parse_mode: str = "Markdown") -> None:
    if not text:
        await message.reply("⚠️ Получен пустой ответ от AI.")
        return
    
    text = clean_markdown(text)
    MAX_LENGTH = 4000
    
    if len(text) <= MAX_LENGTH:
        try:
            await message.reply(text, parse_mode=parse_mode)
        except Exception:
            await message.reply(text, parse_mode=None)
        return
    
    parts = []
    current_part = ""
    for line in text.split('\n'):
        if len(current_part) + len(line) + 1 > MAX_LENGTH:
            parts.append(current_part)
            current_part = line
        else:
            current_part += line + '\n'
    if current_part:
        parts.append(current_part)
    
    for i, part in enumerate(parts, 1):
        try:
            header = f"📄 *Часть {i} из {len(parts)}*\n\n"
            full_part = header + part
            if len(full_part) > MAX_LENGTH:
                full_part = part[:MAX_LENGTH] + "\n\n... (обрезано)"
            await message.reply(full_part, parse_mode=parse_mode)
            await asyncio.sleep(0.5)
        except Exception:
            await message.reply(part, parse_mode=None)

# ===== КЛАВИАТУРЫ =====

def get_main_keyboard():
    kb = [
        [InlineKeyboardButton(text="🤖 AI Консультант", callback_data="ai_consultant")],
        [InlineKeyboardButton(text="📊 Анализ документа", callback_data="analyze_doc")],
        [InlineKeyboardButton(text="💡 Генератор идей", callback_data="idea_gen")],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_back_keyboard():
    kb = [[InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main")]]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_idea_type_keyboard():
    kb = [
        [InlineKeyboardButton(text="📈 Бизнес-стратегия", callback_data="idea_strategy")],
        [InlineKeyboardButton(text="📣 Маркетинговый план", callback_data="idea_marketing")],
        [InlineKeyboardButton(text="🏷️ Название для продукта", callback_data="idea_name")],
        [InlineKeyboardButton(text="🔍 Идеальная ниша", callback_data="idea_niche")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_profile_keyboard():
    kb = [
        [InlineKeyboardButton(text="💎 Купить премиум", callback_data="buy_premium")],
        [InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data="leave_review")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ===== ДЕКОРАТОР ПРОВЕРКИ ЛИМИТОВ =====

def check_limits(func):
    async def wrapper(message: Message, state: FSMContext):
        user_id = message.from_user.id
        can_request, msg = db.can_make_request(user_id)
        
        if not can_request:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Купить премиум", callback_data="buy_premium")]
            ])
            await message.reply(
                f"{msg}\n\nНажмите на кнопку ниже, чтобы получить неограниченный доступ:",
                reply_markup=kb
            )
            return
        
        db.increment_requests(user_id)
        return await func(message, state)
    return wrapper

# ======================================================
#  КОМАНДЫ
# ======================================================

@dp.message(Command("start"))
async def start_command(message: Message):
    user = message.from_user
    
    args = message.text.split()
    referred_by = None
    if len(args) > 1 and args[1].startswith("ref_"):
        ref_code = args[1].replace("ref_", "")
        referrer = db.get_user_by_referral_code(ref_code)
        if referrer:
            referred_by = referrer['user_id']
    
    db.create_or_update_user(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        referred_by=referred_by
    )
    
    reviews = db.get_reviews(3)
    reviews_text = ""
    if reviews:
        reviews_text = "\n\n⭐ *Что говорят наши пользователи:*\n"
        for review in reviews:
            stars = "⭐" * review[2]
            reviews_text += f"\n• {stars} *{review[0]}*: {review[1]}"
    
    welcome_text = (
        "👑 *Добро пожаловать в AI Империю!*\n\n"
        "🚀 *Ваш персональный AI-ассистент для бизнеса*\n\n"
        "💡 *Что я умею:*\n"
        "• 🤖 Отвечать на бизнес-вопросы\n"
        "• 📊 Анализировать документы (PDF)\n"
        "• 💡 Генерировать идеи и стратегии\n\n"
        f"🎁 У вас есть *10 бесплатных запросов в день*.\n"
        "💎 Приобретите премиум за 10 ⭐ и получите неограниченный доступ!\n\n"
        "💬 *Просто напишите мне любой вопрос* — я отвечу как AI-консультант!\n"
        f"{reviews_text}\n\n"
        "👇 *Или выберите действие в меню:*"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.message(Command("help"))
async def help_command(message: Message):
    help_text = (
        "🆘 *Помощь*\n\n"
        "• /start — главное меню\n"
        "• 🤖 AI Консультант — задайте бизнес-вопрос\n"
        "• 📊 Анализ документа — отправьте PDF для анализа\n"
        "• 💡 Генератор идей — создайте стратегию или план\n"
        "• 👤 Мой профиль — посмотрите статус и лимиты\n\n"
        "💎 Премиум дает неограниченный доступ ко всем функциям."
    )
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("admin"))
async def admin_panel(message: Message):
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
        "🔧 *Команды для управления:*\n"
        "• `/extend ID` — продлить подписку на 30 дней\n"
        "• `/disable ID` — отключить подписку\n\n"
        "📋 *Список пользователей:*"
    )
    
    # Показываем первых 10 пользователей
    users = db.get_all_users()
    if users:
        for i, user in enumerate(users[:10], 1):
            status = "💎" if user[2] == 'premium' else "🆓"
            text += f"\n{i}. {status} {user[1]} (ID: `{user[0]}`) | {user[3]} запросов"
        if len(users) > 10:
            text += f"\n\n... и еще {len(users) - 10} пользователей"
    else:
        text += "\n\nПользователей пока нет."
    
    await message.answer(text, parse_mode="Markdown")

# ======================================================
#  КОМАНДЫ УПРАВЛЕНИЯ ПОДПИСКАМИ
# ======================================================

@dp.message(Command("extend"))
async def admin_extend_command(message: Message):
    """Продлевает подписку: /extend 271725844"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите ID пользователя. Пример: /extend 271725844")
        return
    
    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("❌ Неверный ID. Пример: /extend 271725844")
        return
    
    success = db.extend_subscription(user_id, 30)
    
    if success:
        user = db.get_user(user_id)
        await message.answer(
            f"✅ *Подписка продлена на 30 дней!*\n\n"
            f"👤 Пользователь: {user['full_name']}\n"
            f"🆔 ID: `{user_id}`\n"
            f"💎 Статус: Премиум\n"
            f"⏳ Действует до: {user['subscription_end']}",
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Ошибка! Пользователь не найден.")

@dp.message(Command("disable"))
async def admin_disable_command(message: Message):
    """Отключает подписку: /disable 271725844"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите ID пользователя. Пример: /disable 271725844")
        return
    
    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("❌ Неверный ID. Пример: /disable 271725844")
        return
    
    success = db.disable_subscription(user_id)
    
    if success:
        user = db.get_user(user_id)
        await message.answer(
            f"❌ *Подписка отключена!*\n\n"
            f"👤 Пользователь: {user['full_name']}\n"
            f"🆔 ID: `{user_id}`\n"
            f"🆓 Статус: Бесплатный",
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Ошибка! Пользователь не найден.")

# ======================================================
#  ОБРАБОТЧИКИ ИНЛАЙН-КНОПОК
# ======================================================

@dp.callback_query(F.data == "ai_consultant")
async def ai_consultant_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_for_question)
    await callback.message.edit_text(
        "🤖 *AI Консультант*\n\nЗадайте свой бизнес-вопрос. Я постараюсь дать максимально полезный ответ.\n\n"
        "💬 *Или просто напишите любой вопрос в чат* — я отвечу!",
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "analyze_doc")
async def analyze_doc_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_for_document)
    await callback.message.edit_text(
        "📊 *Анализ документов*\n\nОтправьте мне **PDF-файл** (до 5 МБ).\n\nЯ извлеку из него текст и сделаю профессиональный анализ:\n"
        "• Основную суть\n"
        "• Ключевые идеи\n"
        "• Потенциальные риски\n"
        "• Рекомендации для бизнеса\n\n"
        "⏳ Анализ может занять до 30 секунд.",
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "idea_gen")
async def idea_gen_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "💡 *Генератор идей*\n\nВыберите тип идеи, которую хотите получить:",
        reply_markup=get_idea_type_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("idea_"))
async def idea_type_selected(callback: CallbackQuery, state: FSMContext):
    idea_type = callback.data.replace("idea_", "")
    await state.update_data(idea_type=idea_type)
    await state.set_state(Form.waiting_for_idea_topic)
    
    type_names = {
        'strategy': '📈 Бизнес-стратегия',
        'marketing': '📣 Маркетинговый план',
        'name': '🏷️ Название для продукта',
        'niche': '🔍 Идеальная ниша'
    }
    
    await callback.message.edit_text(
        f"💡 *{type_names.get(idea_type, 'Генератор идей')}*\n\n"
        f"Напишите **тему** или сферу, для которой нужно сгенерировать идею.\n\n"
        f"Например:\n"
        f"• *Онлайн-образование для детей*\n"
        f"• *Экологичные товары для дома*\n"
        f"• *Франшиза кофейни*\n\n"
        f"Или просто опишите, что вас интересует.",
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = db.get_user(user_id)
    
    if not user_data:
        await callback.message.edit_text(
            "Пользователь не найден. Напишите /start для регистрации.",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    if user_data['subscription_status'] == 'premium':
        subscription_end = user_data.get('subscription_end')
        if subscription_end and datetime.now().date() > datetime.fromisoformat(subscription_end).date():
            with sqlite3.connect(db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET subscription_status = 'free', subscription_end = NULL WHERE user_id = ?",
                    (user_id,)
                )
                conn.commit()
            user_data = db.get_user(user_id)
    
    status_emoji = "💎" if user_data['subscription_status'] == 'premium' else "🆓"
    status_text = "Премиум" if user_data['subscription_status'] == 'premium' else "Бесплатный"
    
    remaining = db.get_daily_requests_left(user_id)
    if remaining == -1:
        requests_text = "♾️ Безлимит"
    else:
        requests_text = f"{remaining} / 10"
    
    referral_link = db.get_referral_link(user_id)
    
    profile_text = (
        f"👤 *Ваш профиль*\n\n"
        f"• 🆔 ID: `{user_id}`\n"
        f"• 👤 Имя: {callback.from_user.full_name}\n"
        f"• {status_emoji} Статус: *{status_text}*\n"
        f"• 📊 Запросов сегодня: {requests_text}\n"
        f"• 📈 Всего запросов: {user_data['total_requests'] or 0}\n"
        f"• 📅 Дата регистрации: {user_data['registered_at'][:10]}\n"
        f"• 👥 Привел друзей: {user_data.get('referral_count', 0)}\n"
        f"• 🎁 Бонусных запросов: {user_data.get('bonus_requests', 0)}\n\n"
        f"🔗 *Ваша реферальная ссылка:*\n`{referral_link}`\n\n"
        f"👥 *Приведи друга и получи 5 бонусных запросов!*"
    )
    
    if user_data['subscription_status'] == 'premium':
        subscription_end = user_data.get('subscription_end')
        if subscription_end:
            profile_text += f"\n\n⏳ Подписка до: {subscription_end}"
    else:
        profile_text += (
            "\n\n💡 *У вас 10 бесплатных запросов в день*\n"
            "💰 Купите премиум подписку и получите:\n"
            "• ♾️ Неограниченные запросы\n"
            "• 🚀 Приоритетная обработка\n"
            "• 🆕 Ранний доступ к новым функциям"
        )
    
    await callback.message.edit_text(
        profile_text,
        reply_markup=get_profile_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "leave_review")
async def leave_review_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_for_review)
    await callback.message.edit_text(
        "⭐ *Оставьте отзыв*\n\n"
        "Напишите ваш отзыв о боте.\n"
        "Мы будем очень благодарны за обратную связь! 🙏\n\n"
        "Также вы можете оценить бота по шкале от 1 до 5.\n"
        "Напишите что-то вроде:\n"
        "*Отличный бот! Очень помог с бизнес-стратегией. Оценка: 5*",
        reply_markup=get_back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "👑 *Главное меню*\n\nВыберите, что вас интересует:",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

# ======================================================
#  ОБРАБОТЧИКИ ОПЛАТЫ
# ======================================================

@dp.callback_query(F.data == "buy_premium")
async def buy_premium_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = db.get_user(user_id)
    
    if user_data and user_data['subscription_status'] == 'premium':
        subscription_end = user_data.get('subscription_end', 'неизвестно')
        await callback.message.edit_text(
            "💎 *У вас уже есть премиум подписка!*\n\n"
            f"⏳ Действует до: {subscription_end}\n\n"
            "Вы пользуетесь всеми преимуществами:\n"
            "• ♾️ Неограниченные запросы\n"
            "• 📊 Анализ документов\n"
            "• 💡 Генератор идей\n"
            "• 🚀 Приоритетная обработка\n\n"
            "Спасибо, что с нами! 🙌",
            reply_markup=get_back_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return
    
    tariff_text = (
        "💎 *Премиум подписка AI Империя*\n\n"
        "🚀 *Получите неограниченный доступ ко всем функциям!*\n\n"
        "📊 *Бесплатный тариф* — `0 ₽`\n"
        "• 🤖 10 запросов в день\n"
        "• 📊 Анализ документов (PDF)\n"
        "• 💡 Генератор идей\n"
        "• ⏳ Обычная скорость\n\n"
        "🔥 *Премиум тариф* — `10 ⭐/месяц`\n"
        "• ♾️ *Неограниченные запросы*\n"
        "• 📊 *Анализ документов без лимитов*\n"
        "• 💡 *Генератор идей без ограничений*\n"
        "• 🚀 *Приоритетная обработка запросов*\n"
        "• 🆕 *Ранний доступ к новым функциям*\n"
        "• 🎯 *Персональные рекомендации*\n\n"
        "📈 *Для бизнеса:*\n"
        "• Экономия времени на аналитике\n"
        "• Профессиональные стратегии\n"
        "• Маркетинговые планы под ключ\n\n"
        "💳 *Оплата через Telegram Stars*\n"
        "Всего 10 ⭐ за целый месяц!\n"
        "Безопасно, быстро, просто.\n\n"
        "👇 *Нажмите кнопку ниже для покупки*"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Купить премиум за 10 ⭐", callback_data="pay_premium")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(
        tariff_text,
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "pay_premium")
async def pay_premium_callback(callback: CallbackQuery):
    if not PREMIUM_PRODUCT_ID:
        await callback.message.edit_text(
            "⚠️ Оплата временно недоступна. Пожалуйста, попробуйте позже.",
            reply_markup=get_back_keyboard()
        )
        await callback.answer()
        return
    
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="💎 Премиум подписка AI Империя",
        description="Неограниченный доступ ко всем функциям бота на 30 дней.\n\n"
                    "• ♾️ Безлимитные запросы\n"
                    "• 📊 Анализ документов\n"
                    "• 💡 Генератор идей\n"
                    "• 🚀 Приоритетная обработка\n"
                    "• 🆕 Ранний доступ к новым функциям",
        payload="premium_subscription_30days",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="30 дней премиум доступа", amount=10)],
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        is_flexible=False,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    user_id = message.from_user.id
    payment = message.successful_payment
    
    premium_until = datetime.now() + timedelta(days=30)
    premium_until_str = premium_until.date().isoformat()
    
    with sqlite3.connect(db.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE users 
               SET subscription_status = 'premium', 
                   subscription_end = ?,
                   daily_requests = 0,
                   last_request_date = ?
               WHERE user_id = ?""",
            (premium_until_str, datetime.now().date().isoformat(), user_id)
        )
        conn.commit()
    
    await message.answer(
        f"🎉 *Поздравляю!*\n\n"
        f"Вы успешно приобрели **премиум подписку**!\n\n"
        f"💰 Сумма: {payment.total_amount // 100} ⭐\n"
        f"⏳ Действует до: {premium_until_str}\n\n"
        f"🔥 Теперь у вас **неограниченный доступ** ко всем функциям бота!\n\n"
        f"Начните использовать AI прямо сейчас 👇",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
    
    logger.info(f"Пользователь {user_id} купил премиум подписку. Действует до {premium_until_str}")

# ======================================================
#  ОБРАБОТЧИКИ СООБЩЕНИЙ
# ======================================================

@dp.message(Form.waiting_for_question, F.text)
@check_limits
async def handle_ai_question(message: Message, state: FSMContext):
    user_question = message.text

    if user_question.lower() in ["⬅️ назад в меню", "назад", "выход"]:
        await state.clear()
        await message.answer("Вы вернулись в главное меню.", reply_markup=get_main_keyboard())
        return

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    ai_response = ai_assistant.get_response(user_question)
    await safe_send_message(message, ai_response)

@dp.message(Form.waiting_for_idea_topic, F.text)
@check_limits
async def handle_idea_topic(message: Message, state: FSMContext):
    topic = message.text

    if topic.lower() in ["⬅️ назад в меню", "назад", "выход"]:
        await state.clear()
        await message.answer("Вы вернулись в главное меню.", reply_markup=get_main_keyboard())
        return

    data = await state.get_data()
    idea_type = data.get('idea_type', 'стратегия')

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    status_msg = await message.reply("💡 Генерирую идею... Это может занять 10-20 секунд.")

    idea = ai_assistant.generate_idea(idea_type, topic)

    await status_msg.delete()
    await safe_send_message(message, f"💡 *Ваша идея*\n\n{idea}")

@dp.message(Form.waiting_for_document, F.document)
@check_limits
async def handle_document(message: Message, state: FSMContext):
    if not message.document.file_name.endswith('.pdf'):
        await message.reply("❌ Пожалуйста, отправьте файл в формате **PDF**.")
        return

    if message.document.file_size > 5 * 1024 * 1024:
        await message.reply("❌ Слишком большой файл. Максимальный размер — 5 МБ.")
        return

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    status_msg = await message.reply("📄 Начинаю анализ документа. Это может занять до 30 секунд...")

    try:
        file = await bot.get_file(message.document.file_id)
        file_content = await bot.download_file(file.file_path)

        analysis = ai_assistant.analyze_document(
            file_content.read(),
            message.document.file_name
        )

        await status_msg.delete()
        await safe_send_message(message, f"📊 *Анализ документа*\n\n{analysis}")

    except Exception as e:
        await status_msg.delete()
        logger.error(f"Ошибка при обработке документа: {e}")
        await message.reply(f"❌ Произошла ошибка при анализе документа. Попробуйте позже.")

@dp.message(Form.waiting_for_review, F.text)
async def handle_review(message: Message, state: FSMContext):
    review_text = message.text

    if review_text.lower() in ["⬅️ назад в меню", "назад", "выход"]:
        await state.clear()
        await message.answer("Вы вернулись в главное меню.", reply_markup=get_main_keyboard())
        return

    rating = 5
    rating_match = re.search(r'оценк[ау]\s*[:\-]?\s*(\d)', review_text, re.IGNORECASE)
    if rating_match:
        rating = int(rating_match.group(1))
        rating = max(1, min(5, rating))

    clean_review = re.sub(r'оценк[ау]\s*[:\-]?\s*\d', '', review_text, flags=re.IGNORECASE).strip()
    if not clean_review:
        clean_review = review_text

    db.add_review(
        user_id=message.from_user.id,
        username=message.from_user.username or message.from_user.full_name,
        review_text=clean_review,
        rating=rating
    )

    await state.clear()

    stars = "⭐" * rating
    await message.answer(
        f"🙏 *Спасибо за ваш отзыв!*\n\n"
        f"⭐ Ваша оценка: {stars}\n"
        f"📝 Ваш отзыв: \"{clean_review}\"\n\n"
        f"Ваше мнение очень важно для нас! ❤️",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )

# ======================================================
#  ГЛАВНЫЙ ОБРАБОТЧИК ДЛЯ ЛЮБЫХ СООБЩЕНИЙ
# ======================================================

@dp.message(F.text)
async def handle_any_message(message: Message, state: FSMContext):
    user_question = message.text
    
    if user_question.startswith('/'):
        return
    
    can_request, msg = db.can_make_request(message.from_user.id)
    
    if not can_request:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Купить премиум", callback_data="buy_premium")]
        ])
        await message.reply(
            f"{msg}\n\nНажмите на кнопку ниже, чтобы получить неограниченный доступ:",
            reply_markup=kb
        )
        return
    
    db.increment_requests(message.from_user.id)
    
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    ai_response = ai_assistant.get_response(user_question)
    await safe_send_message(message, ai_response)

# ======================================================
#  ЗАПУСК
# ======================================================

async def main():
    print("🚀 Бот AI Империя запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
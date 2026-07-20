from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router()

class AIChatStates(StatesGroup):
    waiting_for_question = State()

@router.callback_query(F.data == "ai_consultant")
async def ai_consultant_start(callback: CallbackQuery, state: FSMContext):
    print("🔵 НАЖАТА КНОПКА AI")
    await state.set_state(AIChatStates.waiting_for_question)
    await callback.message.edit_text(
        "🤖 *AI Консультант (ТЕСТ)*\n\n"
        "Напишите свой вопрос.\n"
        "Для выхода нажмите ⬅️ Назад.",
        parse_mode="Markdown"
    )
    await callback.answer()

@router.message(AIChatStates.waiting_for_question, F.text)
async def handle_ai_question(message: Message, state: FSMContext):
    print(f"🟢 ПОЛУЧЕНО СООБЩЕНИЕ: {message.text}")
    
    if message.text.lower() in ["⬅️ назад", "назад", "выход"]:
        await state.clear()
        await message.answer("Вы вышли из режима AI.")
        return
    
    await message.reply(f"✅ Тест: Вы написали: '{message.text}'. Бот работает!")

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    from bot import get_main_inline_keyboard
    await callback.message.edit_text(
        "👋 *Главное меню*\n\nВыберите действие:",
        reply_markup=get_main_inline_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()
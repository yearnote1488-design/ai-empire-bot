from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="💼 Бизнес"),
            KeyboardButton(text="📈 Маркетинг")
        ],
        [
            KeyboardButton(text="🤖 AI Консультант"),
            KeyboardButton(text="💰 Финансы")
        ],
        [
            KeyboardButton(text="👤 Кабинет"),
            KeyboardButton(text="⚙️ Настройки")
        ]
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите раздел..."
)
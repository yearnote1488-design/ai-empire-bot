from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

business_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="💡 Бизнес-идея"),
            KeyboardButton(text="📄 Бизнес-план")
        ],
        [
            KeyboardButton(text="📊 SWOT-анализ"),
            KeyboardButton(text="🏢 Конкуренты")
        ],
        [
            KeyboardButton(text="📈 Масштабирование")
        ],
        [
            KeyboardButton(text="⬅️ Назад")
        ]
    ],
    resize_keyboard=True
)
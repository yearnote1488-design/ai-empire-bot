import os
import logging
import requests
import PyPDF2
import re
from io import BytesIO

logger = logging.getLogger(__name__)

class AIChat:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY не найден!")

    def _beautify_response(self, text: str) -> str:
        """
        Украшает ответ AI: добавляет эмодзи, форматирует заголовки и списки
        """
        lines = text.split('\n')
        new_lines = []
        
        # Словарь эмодзи для ключевых слов
        emoji_map = {
            'цель': '🎯',
            'задача': '📋',
            'стратеги': '📈',
            'анализ': '📊',
            'маркетинг': '📣',
            'реклама': '📢',
            'бюджет': '💰',
            'прибыль': '💵',
            'доход': '💰',
            'расход': '💸',
            'ресурс': '⚡',
            'команда': '👥',
            'клиент': '👤',
            'аудитория': '👥',
            'конкурент': '⚔️',
            'рынок': '🌍',
            'продукт': '📦',
            'услуг': '🛠️',
            'ниша': '🎯',
            'идея': '💡',
            'план': '📋',
            'срок': '⏰',
            'результат': '🏆',
            'успех': '⭐',
            'риск': '⚠️',
            'рекомендац': '💎',
            'вывод': '📌',
            'шаг': '🚀',
            'этап': '📆',
            'инструмент': '🔧',
            'канал': '📡',
            'контент': '📝',
            'соцсети': '📱',
            'сайт': '🌐',
            'email': '✉️',
            'обучение': '📚',
            'развитие': '🌱',
            'масштабирован': '📈',
            'автоматизаци': '🤖',
            'инвестици': '💎',
            'партнер': '🤝',
            'крипто': '🪙',
            'тренд': '📊'
        }
        
        for line in lines:
            line = line.strip()
            if not line:
                new_lines.append('')
                continue
            
            # Пропускаем строки с эмодзи (они уже украшены)
            if re.search(r'[\U00010000-\U0010ffff]', line):
                new_lines.append(line)
                continue
            
            # Проверяем, является ли строка заголовком (содержит : или начинается с цифры/буквы)
            is_header = False
            
            # Жирный текст с двоеточием - это заголовок
            if '**' in line and ':' in line:
                is_header = True
                # Ищем ключевое слово в заголовке
                for keyword, emoji in emoji_map.items():
                    if keyword in line.lower():
                        # Добавляем эмодзи в начало строки, перед жирным текстом
                        if '**' in line:
                            parts = line.split('**')
                            if len(parts) >= 3:
                                line = f"{parts[0]}{emoji} **{parts[1]}**{parts[2]}"
                        break
            
            # Если строка начинается с цифры и точки (список)
            if re.match(r'^\d+\.', line):
                # Добавляем эмодзи для списков
                if '**' not in line:
                    for keyword, emoji in emoji_map.items():
                        if keyword in line.lower():
                            line = f"{emoji} {line}"
                            break
                else:
                    # Добавляем эмодзи перед жирным текстом в списке
                    for keyword, emoji in emoji_map.items():
                        if keyword in line.lower():
                            parts = line.split('**')
                            if len(parts) >= 3:
                                line = f"{parts[0]}{emoji} **{parts[1]}**{parts[2]}"
                            break
            
            # Если строка начинается с "-" или "*" (маркированный список)
            if line.startswith('- ') or line.startswith('* '):
                # Добавляем эмодзи
                if '**' not in line:
                    for keyword, emoji in emoji_map.items():
                        if keyword in line.lower():
                            line = f"{emoji} {line}"
                            break
                # Если не найдено подходящего эмодзи, ставим точку
                if line.startswith('- ') and not any(keyword in line.lower() for keyword in emoji_map):
                    line = f"• {line[2:]}"
                if line.startswith('* ') and not any(keyword in line.lower() for keyword in emoji_map):
                    line = f"• {line[2:]}"
            
            # Если строка жирная и начинается с цифры
            if re.match(r'^\d+\.\s*\*\*', line):
                for keyword, emoji in emoji_map.items():
                    if keyword in line.lower():
                        parts = line.split('**')
                        if len(parts) >= 3:
                            line = f"{parts[0]}{emoji} **{parts[1]}**{parts[2]}"
                        break
            
            new_lines.append(line)
        
        return '\n'.join(new_lines)

    def get_response(self, user_message: str) -> str:
        """Обычный чат с AI"""
        if not self.api_key:
            return "⚠️ API-ключ не настроен."
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"Ты — бизнес-консультант. Отвечай на русском, четко и по делу. Используй эмодзи для украшения ответа, но не переусердствуй.\n\nВопрос: {user_message}"}]}]
        }
        
        try:
            response = requests.post(url, json=payload)
            data = response.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return self._beautify_response(raw_text)
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            return f"❌ Ошибка: {str(e)[:50]}..."

    def analyze_document(self, file_content: bytes, filename: str) -> str:
        """Анализ PDF-документа с украшением ответа"""
        if not self.api_key:
            return "⚠️ API-ключ не настроен."

        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"

            if not text.strip():
                return "❌ Не удалось извлечь текст из документа. Убедитесь, что это не сканированный PDF."

            if len(text) > 5000:
                text = text[:5000] + "\n... (текст обрезан для анализа)"

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": f"""
Ты — профессиональный бизнес-аналитик. Проанализируй следующий документ.

Название файла: {filename}

Содержание документа:
{text}

Дай структурированный анализ. Используй эмодзи для украшения каждого пункта.

1. 📌 **Основная суть** документа (кратко)
2. 🎯 **Ключевые идеи** и выводы
3. ⚠️ **Потенциальные риски** или слабые места (если есть)
4. 💡 **Рекомендации** для бизнеса на основе этого документа

Отвечай на русском языке, четко и профессионально. Используй эмодзи для улучшения читаемости.
"""}]}]
            }

            response = requests.post(url, json=payload)
            data = response.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return self._beautify_response(raw_text)

        except Exception as e:
            logger.error(f"Ошибка при анализе документа: {e}")
            return f"❌ Ошибка при анализе документа: {str(e)[:100]}..."

    def generate_idea(self, idea_type: str, topic: str) -> str:
        """Генерирует бизнес-идею с украшением"""
        if not self.api_key:
            return "⚠️ API-ключ не настроен."

        # Улучшенные промпты с требованием эмодзи
        prompts = {
            'strategy': f"""
Ты — стратегический консультант. Разработай ДЕТАЛЬНУЮ бизнес-стратегию для темы: "{topic}".

Структура ответа:
1. 🎯 **Цель** стратегии
2. 📊 **Анализ ситуации** (рынок, конкуренты, аудитория)
3. 🚀 **Пошаговый план действий** (3-5 шагов)
4. ⏰ **Сроки и этапы** выполнения
5. 💰 **Бюджет и ресурсы** (примерные цифры)
6. 📈 **Ожидаемые результаты** (KPI)

Ответ должен быть максимально практичным, конкретным и полезным для предпринимателя.
Используй эмодзи для каждого пункта, делай ответ визуально привлекательным.
""",
            'marketing': f"""
Ты — маркетолог-стратег. Создай ПОДРОБНЫЙ маркетинговый план для темы: "{topic}".

Структура ответа:
1. 🎯 **Целевая аудитория** (кто, где, потребности)
2. 🏷️ **Позиционирование** (как выделиться)
3. 📣 **Каналы продвижения** (идеальный набор)
4. 💸 **Бюджет на маркетинг** (примерные цифры)
5. 📆 **Дорожная карта** на 3 месяца (помесячно)
6. 📊 **Метрики успеха** (что отслеживать)

Ответ должен быть конкретным и готовым к внедрению.
Используй эмодзи для каждого пункта, делай ответ визуально привлекательным.
""",
            'name': f"""
Ты — креативный нейминг-эксперт. Сгенерируй 10 УНИКАЛЬНЫХ названий для продукта/бизнеса в нише: "{topic}".

Для каждого названия дай:
- ✅ Название (с эмодзи)
- 📖 Значение и почему это название работает
- 🌍 Ассоциации и эмоции

Правила:
- Названия должны быть запоминающимися
- Разнообразие: короткие, составные, абстрактные
- Должны звучать на русском и легко произноситься

Также в конце выдели ТОП-3 названия и обоснуй выбор.
Используй эмодзи для каждого пункта, делай ответ визуально привлекательным.
""",
            'niche': f"""
Ты — бизнес-аналитик. Найди ИДЕАЛЬНУЮ нишу для бизнеса в сфере: "{topic}".

Структура ответа:
1. 📊 **Анализ рынка** в этой сфере (размер, тренды, проблемы)
2. 🎯 **Перспективные ниши** (минимум 3 варианта)
3. 👥 **Портрет клиента** в каждой нише
4. ⚔️ **Конкуренция** и как войти
5. 💰 **Потенциальная прибыль** и модель монетизации
6. 🚀 **С чего начать** (первые шаги)

Ответ должен быть максимально полезным для выбора направления.
Используй эмодзи для каждого пункта, делай ответ визуально привлекательным.
"""
        }

        prompt = prompts.get(idea_type, f"Сгенерируй креативную бизнес-идею на тему: {topic}. Используй эмодзи для украшения ответа.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }

        try:
            response = requests.post(url, json=payload)
            data = response.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return self._beautify_response(raw_text)
        except Exception as e:
            logger.error(f"Ошибка при генерации идеи: {e}")
            return f"❌ Ошибка при генерации идеи: {str(e)[:100]}..."
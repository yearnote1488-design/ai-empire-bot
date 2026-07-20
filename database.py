import sqlite3
import datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.db_path = Path(__file__).parent / 'data' / 'users.db'
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_db()
        self._migrate_db()
    
    def _get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    subscription_status TEXT DEFAULT 'free',
                    subscription_end DATE,
                    daily_requests INTEGER DEFAULT 0,
                    last_request_date DATE,
                    total_requests INTEGER DEFAULT 0,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    referral_code TEXT,
                    referred_by INTEGER,
                    referral_count INTEGER DEFAULT 0,
                    bonus_requests INTEGER DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    review_text TEXT,
                    rating INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_approved INTEGER DEFAULT 1
                )
            ''')
            
            conn.commit()
            logger.info("✅ База данных инициализирована")
    
    def _migrate_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'referral_code' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN referral_code TEXT")
            if 'referred_by' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
            if 'referral_count' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0")
            if 'bonus_requests' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN bonus_requests INTEGER DEFAULT 0")
            
            conn.commit()
    
    def get_user(self, user_id: int) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None
    
    def get_user_by_referral_code(self, referral_code: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE referral_code = ?", (referral_code,))
            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None
    
    def create_or_update_user(self, user_id: int, username: str = None, full_name: str = None, referred_by: int = None) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            existing = self.get_user(user_id)
            
            if existing:
                if username or full_name:
                    cursor.execute(
                        "UPDATE users SET username = COALESCE(?, username), full_name = COALESCE(?, full_name) WHERE user_id = ?",
                        (username, full_name, user_id)
                    )
                    conn.commit()
                return self.get_user(user_id)
            else:
                referral_code = f"AI{user_id % 10000:04d}"
                while self.get_user_by_referral_code(referral_code):
                    referral_code = f"AI{user_id % 10000:04d}{datetime.datetime.now().second % 10}"
                
                cursor.execute(
                    """INSERT INTO users 
                       (user_id, username, full_name, referral_code, referred_by, bonus_requests) 
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (user_id, username, full_name, referral_code, referred_by, 3 if referred_by else 0)
                )
                conn.commit()
                
                if referred_by:
                    cursor.execute(
                        "UPDATE users SET referral_count = referral_count + 1, bonus_requests = bonus_requests + 5 WHERE user_id = ?",
                        (referred_by,)
                    )
                    conn.commit()
                
                return self.get_user(user_id)
    
    def can_make_request(self, user_id: int) -> tuple[bool, str]:
        user = self.get_user(user_id)
        if not user:
            return False, "Пользователь не найден. Напишите /start для регистрации."
        
        if user.get('bonus_requests', 0) > 0:
            return True, f"Бонусных запросов: {user['bonus_requests']}"
        
        if user['subscription_status'] == 'premium':
            return True, "Премиум доступ"
        
        today = datetime.date.today().isoformat()
        last_date = user.get('last_request_date')
        
        if last_date != today:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET daily_requests = 0, last_request_date = ? WHERE user_id = ?",
                    (today, user_id)
                )
                conn.commit()
            user['daily_requests'] = 0
        
        if user['daily_requests'] >= 10:
            return False, "🚫 Вы исчерпали лимит бесплатных запросов на сегодня (10/10)."
        
        return True, f"Осталось запросов: {10 - user['daily_requests']}"
    
    def increment_requests(self, user_id: int) -> None:
        today = datetime.date.today().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            user = self.get_user(user_id)
            
            if user and user.get('bonus_requests', 0) > 0:
                cursor.execute(
                    "UPDATE users SET bonus_requests = bonus_requests - 1, total_requests = total_requests + 1 WHERE user_id = ?",
                    (user_id,)
                )
                conn.commit()
                return
            
            if user and user['last_request_date'] != today:
                cursor.execute(
                    "UPDATE users SET daily_requests = 0, last_request_date = ? WHERE user_id = ?",
                    (today, user_id)
                )
                conn.commit()
            cursor.execute(
                "UPDATE users SET daily_requests = daily_requests + 1, total_requests = total_requests + 1 WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
    
    def get_daily_requests_left(self, user_id: int) -> int:
        user = self.get_user(user_id)
        if not user:
            return 0
        
        if user.get('bonus_requests', 0) > 0:
            return user['bonus_requests']
        
        if user['subscription_status'] == 'premium':
            return -1
        
        today = datetime.date.today().isoformat()
        if user['last_request_date'] != today:
            return 10
        return max(0, 10 - user['daily_requests'])
    
    def get_referral_link(self, user_id: int) -> str:
        user = self.get_user(user_id)
        if not user:
            return ""
        
        referral_code = user.get('referral_code')
        
        if not referral_code:
            referral_code = f"AI{user_id % 10000:04d}"
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users WHERE referral_code = ? AND user_id != ?", (referral_code, user_id))
                if cursor.fetchone():
                    referral_code = f"AI{user_id % 10000:04d}{datetime.datetime.now().second % 10}"
                cursor.execute(
                    "UPDATE users SET referral_code = ? WHERE user_id = ?",
                    (referral_code, user_id)
                )
                conn.commit()
        
        return f"https://t.me/AIIEmpire_bot?start=ref_{referral_code}"
    
    def add_review(self, user_id: int, username: str, review_text: str, rating: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO reviews (user_id, username, review_text, rating, is_approved) VALUES (?, ?, ?, ?, 0)",
                (user_id, username, review_text, rating)
            )
            conn.commit()
    
    def get_reviews(self, limit: int = 5) -> list:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT username, review_text, rating, created_at FROM reviews WHERE is_approved = 1 ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return rows
    
    # ===== АДМИН-МЕТОДЫ =====
    
    def get_all_users(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, full_name, subscription_status, total_requests, registered_at FROM users ORDER BY registered_at DESC")
            return cursor.fetchall()
    
    def get_stats(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE subscription_status = 'premium'")
            premium_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(total_requests) FROM users")
            total_requests = cursor.fetchone()[0] or 0
            
            revenue = premium_users * 10
            
            return {
                'total_users': total_users,
                'premium_users': premium_users,
                'total_requests': total_requests,
                'revenue': revenue
            }
    
    def toggle_subscription(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if user['subscription_status'] == 'premium':
                cursor.execute(
                    "UPDATE users SET subscription_status = 'free', subscription_end = NULL WHERE user_id = ?",
                    (user_id,)
                )
            else:
                end_date = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
                cursor.execute(
                    "UPDATE users SET subscription_status = 'premium', subscription_end = ? WHERE user_id = ?",
                    (end_date, user_id)
                )
            conn.commit()
            return True
    
    def get_unapproved_reviews(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, review_text, rating, created_at FROM reviews WHERE is_approved = 0 ORDER BY created_at DESC"
            )
            return cursor.fetchall()
    
    def approve_review(self, review_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE reviews SET is_approved = 1 WHERE id = ?",
                (review_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_review(self, review_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    # ===== НОВЫЕ МЕТОДЫ ДЛЯ УПРАВЛЕНИЯ ПОДПИСКАМИ =====
    
    def get_user_by_id_or_name(self, search: str) -> list:
        """Ищет пользователей по ID или имени"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                user_id = int(search)
                cursor.execute(
                    "SELECT user_id, full_name, subscription_status, subscription_end, total_requests FROM users WHERE user_id = ?",
                    (user_id,)
                )
            except ValueError:
                cursor.execute(
                    "SELECT user_id, full_name, subscription_status, subscription_end, total_requests FROM users WHERE full_name LIKE ?",
                    (f"%{search}%",)
                )
            return cursor.fetchall()
    
    def extend_subscription(self, user_id: int, days: int = 30) -> bool:
        """Продлевает подписку на указанное количество дней"""
        user = self.get_user(user_id)
        if not user:
            return False
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if user['subscription_status'] == 'premium' and user.get('subscription_end'):
                current_end = datetime.date.fromisoformat(user['subscription_end'])
                new_end = current_end + datetime.timedelta(days=days)
                new_end_str = new_end.isoformat()
            else:
                new_end = datetime.date.today() + datetime.timedelta(days=days)
                new_end_str = new_end.isoformat()
                cursor.execute(
                    "UPDATE users SET daily_requests = 0, last_request_date = ? WHERE user_id = ?",
                    (datetime.date.today().isoformat(), user_id)
                )
            
            cursor.execute(
                "UPDATE users SET subscription_status = 'premium', subscription_end = ? WHERE user_id = ?",
                (new_end_str, user_id)
            )
            conn.commit()
            return True
    
    def disable_subscription(self, user_id: int) -> bool:
        """Отключает премиум подписку"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET subscription_status = 'free', subscription_end = NULL WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

db = Database()
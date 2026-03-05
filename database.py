import sqlite3
from datetime import datetime
import threading
import logging
import os
import shutil
from functools import lru_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_file='bot_database.db'):
        self.db_file = db_file
        self.local = threading.local()
        self._init_db()
        self._optimize_db()
        logger.info(f"✅ База данных подключена: {db_file}")

    def _get_connection(self):
        """Получение соединения с БД (одно на поток)"""
        if not hasattr(self.local, 'conn'):
            self.local.conn = sqlite3.connect(self.db_file, check_same_thread=False)
            self.local.conn.row_factory = sqlite3.Row
            # Включаем оптимизации
            self.local.conn.execute('PRAGMA synchronous = NORMAL')
            self.local.conn.execute('PRAGMA journal_mode = WAL')
            self.local.conn.execute('PRAGMA cache_size = 10000')
            self.local.conn.execute('PRAGMA temp_store = MEMORY')
        return self.local.conn

    def _optimize_db(self):
        """Оптимизация базы данных"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Создаем индексы для ускорения поиска
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON profiles(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_purchases_user_id ON purchases(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_purchases_status ON purchases(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_withdrawals_user_id ON withdrawals(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_withdrawals_status ON withdrawals(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_withdrawals_date ON withdrawals(date)')

        conn.commit()
        logger.info("✅ Индексы созданы")

    def _init_db(self):
        """Инициализация таблиц"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Таблица профилей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                reg_date TEXT,
                gold_balance REAL DEFAULT 0,
                total_orders_sum REAL DEFAULT 0,
                total_orders_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'Активен'
            )
        ''')

        # Таблица покупок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                order_number INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                user_id TEXT,
                username TEXT,
                gold_amount REAL,
                rub_amount REAL,
                receipt_photo TEXT,
                status TEXT,
                payment_time TEXT,
                admin_approved TEXT DEFAULT 'Нет',
                FOREIGN KEY (user_id) REFERENCES profiles (user_id) ON DELETE CASCADE
            )
        ''')

        # Таблица выводов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS withdrawals (
                order_number INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                user_id TEXT,
                username TEXT,
                gold_amount REAL,
                rub_amount REAL,
                status TEXT,
                admin_approved TEXT DEFAULT 'Нет',
                FOREIGN KEY (user_id) REFERENCES profiles (user_id) ON DELETE CASCADE
            )
        ''')

        conn.commit()
        logger.info("✅ Таблицы созданы/проверены")

    # ========== РАБОТА С ПРОФИЛЯМИ ==========

    @lru_cache(maxsize=1000)
    def _cached_get_profile(self, user_id):
        """Кэшированный запрос профиля"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (str(user_id),))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_or_create_profile(self, user_id, username, first_name, last_name):
        """Получение или создание профиля (без дубликатов)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Сначала проверяем кэш
        cached = self._cached_get_profile(user_id)
        if cached:
            return cached

        # Ищем в базе
        cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (str(user_id),))
        existing = cursor.fetchone()

        if existing:
            # Если нашли - возвращаем
            profile_dict = dict(existing)
            self._cached_get_profile.cache_clear()
            return profile_dict

        # Если нет - создаем нового
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            cursor.execute('''
                INSERT INTO profiles (user_id, username, first_name, last_name, reg_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (str(user_id), username or '-', first_name or '-', last_name or '-', date))

            conn.commit()
            logger.info(f"✅ Создан новый профиль для пользователя {user_id}")

            # Получаем созданный профиль
            cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (str(user_id),))
            new_profile = cursor.fetchone()

            self._cached_get_profile.cache_clear()
            return dict(new_profile)

        except sqlite3.IntegrityError:
            # Если вдруг кто-то создал параллельно - пробуем получить еще раз
            cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (str(user_id),))
            profile = cursor.fetchone()
            return dict(profile) if profile else None

    def get_user_balance(self, user_id):
        """Быстрое получение баланса"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT gold_balance FROM profiles WHERE user_id = ?', (str(user_id),))
        result = cursor.fetchone()

        return result['gold_balance'] if result else 0

    def update_gold_balance(self, user_id, amount, operation='add'):
        """Обновление баланса"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if operation == 'add':
            cursor.execute('''
                UPDATE profiles 
                SET gold_balance = gold_balance + ?,
                    total_orders_sum = total_orders_sum + ?,
                    total_orders_count = total_orders_count + 1
                WHERE user_id = ?
                RETURNING gold_balance
            ''', (amount, amount * 0.75, str(user_id)))
        elif operation == 'subtract':
            cursor.execute('SELECT gold_balance FROM profiles WHERE user_id = ?', (str(user_id),))
            current = cursor.fetchone()
            if not current or current['gold_balance'] < amount:
                return False

            cursor.execute('''
                UPDATE profiles 
                SET gold_balance = gold_balance - ?
                WHERE user_id = ?
                RETURNING gold_balance
            ''', (amount, str(user_id)))
        else:
            return False

        result = cursor.fetchone()
        conn.commit()

        self._cached_get_profile.cache_clear()

        return result['gold_balance'] if result else False

    # ========== РАБОТА С ПОКУПКАМИ ==========

    def add_purchase_order(self, user_id, username, gold_amount, rub_amount):
        """Добавление заявки на покупку"""
        conn = self._get_connection()
        cursor = conn.cursor()

        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute('''
            INSERT INTO purchases (date, user_id, username, gold_amount, rub_amount, status)
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING order_number
        ''', (date, str(user_id), username, gold_amount, rub_amount, 'Ожидает оплаты'))

        order_number = cursor.fetchone()['order_number']
        conn.commit()

        return order_number

    def update_purchase_receipt(self, order_number, file_id):
        """Обновление фото чека"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE purchases 
            SET receipt_photo = ?, 
                status = 'Ожидает проверки', 
                payment_time = ?
            WHERE order_number = ?
        ''', (file_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), order_number))

        conn.commit()
        return cursor.rowcount > 0

    def update_purchase_status(self, order_number, status, admin_approved='Да'):
        """Обновление статуса покупки"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE purchases 
            SET status = ?, admin_approved = ?
            WHERE order_number = ?
        ''', (status, admin_approved, order_number))

        conn.commit()
        return cursor.rowcount > 0

    def get_purchase_order(self, order_number):
        """Получение данных заказа"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM purchases WHERE order_number = ?', (order_number,))
        row = cursor.fetchone()

        return dict(row) if row else None

    # ========== РАБОТА С ВЫВОДАМИ ==========

    def add_withdrawal_order(self, user_id, username, gold_amount, rub_amount):
        """Добавление заявки на вывод"""
        conn = self._get_connection()
        cursor = conn.cursor()

        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute('''
            INSERT INTO withdrawals (date, user_id, username, gold_amount, rub_amount, status)
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING order_number
        ''', (date, str(user_id), username, gold_amount, rub_amount, 'Ожидает проверки'))

        order_number = cursor.fetchone()['order_number']
        conn.commit()

        return order_number

    def update_withdrawal_status(self, order_number, status, admin_approved='Да'):
        """Обновление статуса вывода"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE withdrawals 
            SET status = ?, admin_approved = ?
            WHERE order_number = ?
        ''', (status, admin_approved, order_number))

        conn.commit()
        return cursor.rowcount > 0

    def get_withdrawal_order(self, order_number):
        """Получение данных вывода"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM withdrawals WHERE order_number = ?', (order_number,))
        row = cursor.fetchone()

        return dict(row) if row else None

    # ========== БЫСТРАЯ ИСТОРИЯ ==========

    def get_user_purchases(self, user_id, limit=50, offset=0):
        """Быстрое получение истории покупок"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT order_number, date, gold_amount, rub_amount, status
            FROM purchases
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT ? OFFSET ?
        ''', (str(user_id), limit, offset))

        return [dict(row) for row in cursor.fetchall()]

    def get_user_withdrawals(self, user_id, limit=50, offset=0):
        """Быстрое получение истории выводов"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT order_number, date, gold_amount, rub_amount, status
            FROM withdrawals
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT ? OFFSET ?
        ''', (str(user_id), limit, offset))

        return [dict(row) for row in cursor.fetchall()]

    def get_user_purchases_count(self, user_id):
        """Получение общего количества покупок пользователя"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM purchases WHERE user_id = ?', (str(user_id),))
        result = cursor.fetchone()

        return result[0] if result else 0

    def get_user_withdrawals_count(self, user_id):
        """Получение общего количества выводов пользователя"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM withdrawals WHERE user_id = ?', (str(user_id),))
        result = cursor.fetchone()

        return result[0] if result else 0
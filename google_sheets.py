import gspread
import os
from datetime import datetime
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GoogleSheetsManager:
    def __init__(self, purchases_id, withdrawals_id, profiles_id):
        """Инициализация подключения к Google Sheets"""
        start_time = time.time()

        try:
            # Указываем путь к credentials.json
            current_dir = os.path.dirname(__file__)
            credentials_path = os.path.join(current_dir, 'credentials.json')

            logger.info(f"🔍 Ищем credentials.json по пути: {credentials_path}")

            # Подключаемся
            gc = gspread.service_account(filename=credentials_path)

            # Открываем таблицы
            self.purchases_sheet = gc.open_by_key(purchases_id)
            self.withdrawals_sheet = gc.open_by_key(withdrawals_id)
            self.profiles_sheet = gc.open_by_key(profiles_id)

            # Берем первый лист
            self.purchases = self.purchases_sheet.sheet1
            self.withdrawals = self.withdrawals_sheet.sheet1
            self.profiles = self.profiles_sheet.sheet1

            # Инициализируем заголовки
            self._init_sheets()

            elapsed = time.time() - start_time
            logger.info(f"✅ Google Sheets подключены успешно за {elapsed:.1f}с")

        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Google Sheets: {e}")
            self.purchases = None
            self.withdrawals = None
            self.profiles = None

    def _init_sheets(self):
        """Инициализация заголовков таблиц"""
        try:
            if self.purchases and not self.purchases.get_all_values():
                headers = ['Заказ N', 'Дата', 'User ID', 'Username', 'Сумма GOLD', 'Сумма RUB',
                           'Фото чека', 'Статус', 'Время оплаты', 'Проверен администратором']
                self.purchases.append_row(headers)
                logger.info("✅ Созданы заголовки в таблице покупок")

            if self.withdrawals and not self.withdrawals.get_all_values():
                headers = ['Заказ M', 'Дата', 'User ID', 'Username', 'Сумма GOLD',
                           'Сумма к выводу (RUB)', 'Статус', 'Проверен администратором']
                self.withdrawals.append_row(headers)
                logger.info("✅ Созданы заголовки в таблице выводов")

            if self.profiles and not self.profiles.get_all_values():
                headers = ['User ID', 'Username', 'First Name', 'Last Name', 'Дата регистрации',
                           'GOLD баланс', 'Сумма заказов (RUB)', 'Количество заказов', 'Статус']
                self.profiles.append_row(headers)
                logger.info("✅ Созданы заголовки в таблице профилей")

        except Exception as e:
            logger.error(f"Ошибка инициализации таблиц: {e}")

    # ========== МЕТОДЫ ДЛЯ ПОКУПОК ==========

    def get_next_order_number(self, sheet_type):
        """Получение следующего номера заказа"""
        try:
            if sheet_type == 'purchase':
                if not self.purchases:
                    return 1
                records = self.purchases.get_all_values()
                if len(records) <= 1:
                    return 1
                max_num = 0
                for row in records[1:]:
                    try:
                        num = int(row[0]) if row[0] else 0
                        max_num = max(max_num, num)
                    except:
                        continue
                return max_num + 1

            elif sheet_type == 'withdrawal':
                if not self.withdrawals:
                    return 1
                records = self.withdrawals.get_all_values()
                if len(records) <= 1:
                    return 1
                max_num = 0
                for row in records[1:]:
                    try:
                        num = int(row[0]) if row[0] else 0
                        max_num = max(max_num, num)
                    except:
                        continue
                return max_num + 1
        except Exception as e:
            logger.error(f"Ошибка получения номера заказа: {e}")
            return 1

    def add_purchase_order(self, user_id, username, gold_amount, rub_amount, order_number):
        """Добавление заявки на покупку"""
        try:
            if not self.purchases:
                logger.warning("⚠️ Таблица покупок не доступна")
                return False

            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row = [str(order_number), date, str(user_id), username or '-', str(gold_amount),
                   f"{rub_amount:.2f}", '', 'Ожидает оплаты', '', 'Нет']
            self.purchases.append_row(row)
            logger.info(f"✅ Заявка на покупку {order_number} добавлена")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления заявки на покупку: {e}")
            return False

    def update_purchase_receipt(self, order_number, file_id):
        """Обновление фото чека в заявке"""
        try:
            if not self.purchases:
                return False

            cell = self.purchases.find(str(order_number))
            if cell:
                self.purchases.update_cell(cell.row, 7, file_id)
                self.purchases.update_cell(cell.row, 8, 'Ожидает проверки')
                payment_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.purchases.update_cell(cell.row, 9, payment_time)
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка обновления чека: {e}")
            return False

    # ========== МЕТОДЫ ДЛЯ ВЫВОДОВ ==========

    def add_withdrawal_order(self, user_id, username, gold_amount, rub_amount, order_number):
        """Добавление заявки на вывод"""
        try:
            if not self.withdrawals:
                logger.warning("⚠️ Таблица выводов не доступна")
                return False

            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row = [str(order_number), date, str(user_id), username or '-', str(gold_amount),
                   f"{rub_amount:.2f}", 'Ожидает проверки', 'Нет']
            self.withdrawals.append_row(row)
            logger.info(f"✅ Заявка на вывод {order_number} добавлена")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления заявки на вывод: {e}")
            return False

    # ========== МЕТОДЫ ДЛЯ ПРОФИЛЕЙ ==========

    def get_or_create_profile(self, user_id, username, first_name, last_name):
        """Получение или создание профиля пользователя"""
        try:
            if not self.profiles:
                logger.warning("⚠️ Таблица профилей не доступна")
                return self._create_test_profile(user_id, username, first_name, last_name)

            # Получаем все записи
            all_records = self.profiles.get_all_values()

            # Ищем пользователя по всей таблице
            for i, row in enumerate(all_records):
                if i == 0:  # Пропускаем заголовки
                    continue
                if len(row) > 0 and row[0] == str(user_id):
                    logger.info(f"✅ Найден существующий профиль для пользователя {user_id}")
                    return {
                        'user_id': row[0],
                        'username': row[1] if len(row) > 1 else '-',
                        'first_name': row[2] if len(row) > 2 else '-',
                        'last_name': row[3] if len(row) > 3 else '-',
                        'reg_date': row[4] if len(row) > 4 else '-',
                        'gold_balance': float(row[5]) if len(row) > 5 and row[5] else 0,
                        'total_orders_sum': float(row[6]) if len(row) > 6 and row[6] else 0,
                        'total_orders_count': int(row[7]) if len(row) > 7 and row[7] else 0,
                        'status': row[8] if len(row) > 8 else 'Активен'
                    }

            # Если не нашли - создаем нового
            logger.info(f"✅ Создаем новый профиль для пользователя {user_id}")
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_row = [str(user_id), username or '-', first_name or '-',
                       last_name or '-', date, '0', '0', '0', 'Активен']

            self.profiles.append_row(new_row)

            return {
                'user_id': str(user_id),
                'username': username or '-',
                'first_name': first_name or '-',
                'last_name': last_name or '-',
                'reg_date': date,
                'gold_balance': 0,
                'total_orders_sum': 0,
                'total_orders_count': 0,
                'status': 'Активен'
            }

        except Exception as e:
            logger.error(f"Ошибка работы с профилем: {e}")
            return self._create_test_profile(user_id, username, first_name, last_name)

    def get_user_balance(self, user_id):
        """Получение баланса пользователя"""
        try:
            if not self.profiles:
                return 0

            all_records = self.profiles.get_all_values()
            for i, row in enumerate(all_records):
                if i == 0:
                    continue
                if len(row) > 0 and row[0] == str(user_id):
                    return float(row[5]) if len(row) > 5 and row[5] else 0
            return 0
        except Exception as e:
            logger.error(f"Ошибка получения баланса: {e}")
            return 0

    def update_gold_balance(self, user_id, amount, operation='add'):
        """Обновление баланса GOLD"""
        try:
            if not self.profiles:
                return False

            all_records = self.profiles.get_all_values()
            for i, row in enumerate(all_records):
                if i == 0:
                    continue
                if len(row) > 0 and row[0] == str(user_id):
                    # Нашли пользователя
                    current_balance = float(row[5]) if len(row) > 5 and row[5] else 0

                    if operation == 'add':
                        new_balance = current_balance + amount
                        # Обновляем статистику заказов
                        current_sum = float(row[6]) if len(row) > 6 and row[6] else 0
                        current_count = int(row[7]) if len(row) > 7 and row[7] else 0
                        self.profiles.update_cell(i + 1, 7, str(current_sum + (amount * 0.75)))
                        self.profiles.update_cell(i + 1, 8, str(current_count + 1))
                    elif operation == 'subtract':
                        if current_balance < amount:
                            return False
                        new_balance = current_balance - amount
                    else:
                        return False

                    self.profiles.update_cell(i + 1, 6, str(new_balance))
                    return new_balance

            return False
        except Exception as e:
            logger.error(f"Ошибка обновления баланса: {e}")
            return False

    def update_order_status(self, sheet_type, order_number, status, admin_approved='Да'):
        """Обновление статуса заказа"""
        try:
            if sheet_type == 'purchase':
                if not self.purchases:
                    return False
                sheet = self.purchases
                cell = sheet.find(str(order_number))
                if cell:
                    sheet.update_cell(cell.row, 8, status)
                    sheet.update_cell(cell.row, 10, admin_approved)
                    return True
            else:
                if not self.withdrawals:
                    return False
                sheet = self.withdrawals
                cell = sheet.find(str(order_number))
                if cell:
                    sheet.update_cell(cell.row, 7, status)
                    sheet.update_cell(cell.row, 8, admin_approved)
                    return True
            return False
        except Exception as e:
            logger.error(f"Ошибка обновления статуса: {e}")
            return False

    def get_user_history(self, user_id, history_type):
        """Получение истории пользователя"""
        try:
            history = []

            if history_type == 'purchases':
                if not self.purchases:
                    return []
                records = self.purchases.get_all_values()[1:]
                for row in records:
                    if len(row) > 2 and row[2] == str(user_id):
                        history.append({
                            'order': row[0],
                            'date': row[1],
                            'gold': row[4],
                            'rub': row[5],
                            'status': row[7]
                        })
            else:
                if not self.withdrawals:
                    return []
                records = self.withdrawals.get_all_values()[1:]
                for row in records:
                    if len(row) > 2 and row[2] == str(user_id):
                        history.append({
                            'order': row[0],
                            'date': row[1],
                            'gold': row[4],
                            'rub': row[5],
                            'status': row[6]
                        })

            history.sort(key=lambda x: x['date'], reverse=True)
            return history
        except Exception as e:
            logger.error(f"Ошибка получения истории: {e}")
            return []

    def _create_test_profile(self, user_id, username, first_name, last_name):
        """Создание тестового профиля при ошибке"""
        return {
            'user_id': str(user_id),
            'username': username or '-',
            'first_name': first_name or '-',
            'last_name': last_name or '-',
            'reg_date': datetime.now().strftime("%Y-%m-%d"),
            'gold_balance': 0,
            'total_orders_sum': 0,
            'total_orders_count': 0,
            'status': 'Активен'
        }

    # ========== МЕТОД ДЛЯ ОЧИСТКИ ДУБЛИКАТОВ ==========

    def clean_duplicate_profiles(self):
        """Очистка дубликатов профилей (запустить один раз)"""
        try:
            if not self.profiles:
                return

            all_records = self.profiles.get_all_values()
            if len(all_records) <= 1:
                return

            headers = all_records[0]
            unique_users = {}

            # Собираем уникальные записи
            for row in all_records[1:]:
                if len(row) < 1:
                    continue

                user_id = row[0]

                # Если такой пользователь уже есть, сравниваем баланс
                if user_id in unique_users:
                    existing = unique_users[user_id]
                    try:
                        existing_balance = float(existing[5]) if len(existing) > 5 and existing[5] else 0
                        new_balance = float(row[5]) if len(row) > 5 and row[5] else 0
                        # Оставляем запись с большим балансом
                        if new_balance > existing_balance:
                            unique_users[user_id] = row
                    except:
                        pass
                else:
                    unique_users[user_id] = row

            # Очищаем и записываем заново
            self.profiles.clear()
            self.profiles.append_row(headers)
            for profile in unique_users.values():
                self.profiles.append_row(profile)

            logger.info(f"✅ Очищено дубликатов. Осталось {len(unique_users)} уникальных профилей")
            return True

        except Exception as e:
            logger.error(f"Ошибка очистки дубликатов: {e}")
            return False
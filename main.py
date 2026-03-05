import telebot
from telebot import types
import threading
import time
from datetime import datetime
import logging
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

from config import *
from database import Database

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)
bot.remove_webhook()

# Инициализация базы данных
db = Database()

# Хранение временных данных
user_data = {}
pending_orders = {}
get_id_mode = {}  # Для режима получения file_id

# Константы
MIN_PURCHASE = 100
MAX_PURCHASE = 10000
WITHDRAWAL_COMMISSION = 0.20  # 20%
FIXED_FEE = 0.04  # 0.04 GOLD


# ================== КЛАСС ДЛЯ УПРАВЛЕНИЯ FILE_ID ==================

class ImageManager:
    def __init__(self):
        self.welcome_file_id = WELCOME_IMAGE_FILE_ID
        self.profile_file_id = PROFILE_IMAGE_FILE_ID
        self.skin_example_file_id = SKIN_EXAMPLE_FILE_ID
        logger.info(f"✅ ImageManager инициализирован: welcome={self.welcome_file_id is not None}, "
                    f"profile={self.profile_file_id is not None}, "
                    f"skin_example={self.skin_example_file_id is not None}")

    def set_welcome_file_id(self, file_id):
        self.welcome_file_id = file_id
        logger.info(f"✅ Установлен welcome file_id: {file_id}")

    def set_profile_file_id(self, file_id):
        self.profile_file_id = file_id
        logger.info(f"✅ Установлен profile file_id: {file_id}")

    def set_skin_example_file_id(self, file_id):
        self.skin_example_file_id = file_id
        logger.info(f"✅ Установлен skin example file_id: {file_id}")

    def send_welcome(self, chat_id, caption):
        """Отправка приветственного фото"""
        if self.welcome_file_id:
            try:
                bot.send_photo(
                    chat_id,
                    self.welcome_file_id,
                    caption=caption,
                    reply_markup=get_main_menu()
                )
                return True
            except Exception as e:
                logger.error(f"Ошибка отправки welcome по file_id: {e}")

        # Если нет file_id или ошибка - пробуем отправить файл
        try:
            if os.path.exists(WELCOME_IMAGE_PATH):
                with open(WELCOME_IMAGE_PATH, 'rb') as photo:
                    msg = bot.send_photo(
                        chat_id,
                        photo,
                        caption=caption,
                        reply_markup=get_main_menu()
                    )
                    self.welcome_file_id = msg.photo[-1].file_id
                    logger.info(f"✅ Получен новый file_id для welcome: {self.welcome_file_id}")
                    return True
        except Exception as e:
            logger.error(f"Ошибка отправки файла welcome: {e}")

        # Если ничего не сработало - отправляем без фото
        bot.send_message(chat_id, caption, reply_markup=get_main_menu())
        return False

    def send_profile(self, chat_id, caption):
        """Отправка фото профиля"""
        if self.profile_file_id:
            try:
                bot.send_photo(
                    chat_id,
                    self.profile_file_id,
                    caption=caption,
                    reply_markup=get_profile_keyboard()
                )
                return True
            except Exception as e:
                logger.error(f"Ошибка отправки profile по file_id: {e}")

        try:
            if os.path.exists(PROFILE_IMAGE_PATH):
                with open(PROFILE_IMAGE_PATH, 'rb') as photo:
                    msg = bot.send_photo(
                        chat_id,
                        photo,
                        caption=caption,
                        reply_markup=get_profile_keyboard()
                    )
                    self.profile_file_id = msg.photo[-1].file_id
                    logger.info(f"✅ Получен новый file_id для profile: {self.profile_file_id}")
                    return True
        except Exception as e:
            logger.error(f"Ошибка отправки файла profile: {e}")

        bot.send_message(chat_id, caption, reply_markup=get_profile_keyboard())
        return False

    def send_skin(self, chat_id, caption):
        """Отправка фото примера скина только по file_id"""
        if self.skin_example_file_id:
            try:
                bot.send_photo(
                    chat_id,
                    self.skin_example_file_id,
                    caption=caption,
                    reply_markup=get_withdrawal_keyboard()
                )
                return True
            except Exception as e:
                logger.error(f"Ошибка отправки skin по file_id: {e}")
                return False
        else:
            logger.warning("❌ skin_example_file_id не установлен")
            return False


# Создаем экземпляр менеджера
image_manager = ImageManager()

# ================== КЭШИРОВАННЫЕ КЛАВИАТУРЫ ==================

_main_menu_keyboard = None
_calculator_keyboard = None
_purchase_keyboard = None
_withdrawal_keyboard = None
_profile_keyboard = None


def get_main_menu():
    global _main_menu_keyboard
    if not _main_menu_keyboard:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        buttons = [
            types.KeyboardButton("💰 Купить GOLD"),
            types.KeyboardButton("💸 Вывести GOLD"),
            types.KeyboardButton("👤 Профиль"),
            types.KeyboardButton("🧮 Калькулятор")
        ]
        keyboard.add(*buttons)
        _main_menu_keyboard = keyboard
    return _main_menu_keyboard


def get_calculator_keyboard():
    global _calculator_keyboard
    if not _calculator_keyboard:
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        buttons = [
            types.InlineKeyboardButton("🍯 GOLD ➡️ ₽", callback_data="calc_gold_to_rub"),
            types.InlineKeyboardButton("₽ ➡️ 🍯 GOLD", callback_data="calc_rub_to_gold"),
            types.InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")
        ]
        keyboard.add(*buttons)
        _calculator_keyboard = keyboard
    return _calculator_keyboard


def get_purchase_keyboard():
    global _purchase_keyboard
    if not _purchase_keyboard:
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        buttons = [
            types.InlineKeyboardButton("✏️ Ввести сумму", callback_data="enter_purchase_amount"),
            types.InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")
        ]
        keyboard.add(*buttons)
        _purchase_keyboard = keyboard
    return _purchase_keyboard


def get_withdrawal_keyboard():
    """Клавиатура для вывода"""
    global _withdrawal_keyboard
    if not _withdrawal_keyboard:
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        buttons = [
            types.InlineKeyboardButton("💎 Скин выставлен", callback_data="skin_placed"),
            types.InlineKeyboardButton("◀️ Отмена", callback_data="back_to_menu")
        ]
        keyboard.add(*buttons)
        _withdrawal_keyboard = keyboard
    return _withdrawal_keyboard


def get_profile_keyboard():
    global _profile_keyboard
    if not _profile_keyboard:
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        buttons = [
            types.InlineKeyboardButton("📜 История покупок", callback_data="history_purchases_1"),
            types.InlineKeyboardButton("📤 История выводов", callback_data="history_withdrawals_1"),
            types.InlineKeyboardButton("🔄 Обновить", callback_data="refresh_profile"),
            types.InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")
        ]
        keyboard.add(*buttons)
        _profile_keyboard = keyboard
    return _profile_keyboard


def get_admin_purchase_keyboard(order_number):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("✅ Принять", callback_data=f"admin_accept_purchase_{order_number}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_reject_purchase_{order_number}")
    ]
    keyboard.add(*buttons)
    return keyboard


def get_admin_withdrawal_keyboard(order_number):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"admin_accept_withdrawal_{order_number}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_reject_withdrawal_{order_number}")
    ]
    keyboard.add(*buttons)
    return keyboard


# ================== ФУНКЦИИ-ОБЕРТКИ ДЛЯ ОТПРАВКИ ФОТО ==================

def send_welcome_photo(chat_id, caption):
    """Отправка приветственного фото"""
    return image_manager.send_welcome(chat_id, caption)


def send_profile_photo(chat_id, caption):
    """Отправка фото профиля"""
    return image_manager.send_profile(chat_id, caption)


# ================== ОБРАБОТЧИК КОМАНДЫ START ==================

@bot.message_handler(commands=['start'])
def start_message(message):
    user = message.from_user
    logger.info(f"Пользователь {user.id} запустил бота")

    # Получаем профиль
    profile = db.get_or_create_profile(user.id, user.username, user.first_name, user.last_name)

    # Отправляем приветствие с фото (если есть file_id)
    caption = f"👋 Добро пожаловать, {user.first_name}!\n\n" \
              f"Курс: 1 GOLD = {GOLD_RATE} ₽\n\n" \
              f"Выберите действие:"

    send_welcome_photo(message.chat.id, caption)


# ================== ПОЛУЧЕНИЕ FILE_ID (ВРЕМЕННЫЙ РЕЖИМ) ==================

@bot.message_handler(commands=['get_id'])
def start_get_id(message):
    """Вход в режим получения file_id"""
    user_id = message.from_user.id

    # Активируем режим для пользователя
    get_id_mode[user_id] = True

    bot.send_message(
        message.chat.id,
        "📸 Режим получения File ID активирован\n\n"
        "Отправляйте мне фото, а я буду показывать его File ID.\n"
        "Команда /stop_get_id - выйти из режима"
    )


@bot.message_handler(commands=['stop_get_id'])
def stop_get_id(message):
    """Выход из режима получения file_id"""
    user_id = message.from_user.id

    if user_id in get_id_mode:
        del get_id_mode[user_id]
        bot.send_message(
            message.chat.id,
            "✅ Режим получения File ID деактивирован"
        )
    else:
        bot.send_message(
            message.chat.id,
            "❌ Режим получения File ID не был активирован"
        )


# ================== ОСНОВНЫЕ КНОПКИ МЕНЮ ==================

@bot.message_handler(func=lambda message: message.text == "💰 Купить GOLD")
def buy_gold(message):
    bot.send_message(
        message.chat.id,
        f"📃 Товар: GOLD\n💰 Цена: {GOLD_RATE} ₽\n\nВыберите количество:",
        reply_markup=get_purchase_keyboard()
    )


@bot.message_handler(func=lambda message: message.text == "💸 Вывести GOLD")
def withdraw_gold(message):
    bot.send_message(
        message.chat.id,
        "🍯 Вывод GOLD\n\nОтправьте сумму:"
    )
    user_data[message.from_user.id] = {'state': 'waiting_withdrawal_amount'}


@bot.message_handler(func=lambda message: message.text == "👤 Профиль")
def show_profile(message):
    user = message.from_user

    profile = db.get_or_create_profile(user.id, user.username, user.first_name, user.last_name)

    text = (
        f"❤️ Никнейм: {profile['username']}\n"
        f"🔑 TG ID: {profile['user_id']}\n"
        f"💎 Статус: {profile['status']}\n"
        f"💰 GOLD: {profile['gold_balance']}\n"
        f"⭐️ Сумма заказов: {profile['total_orders_sum']:.2f} ₽\n"
        f"📃 Заказов: {profile['total_orders_count']}\n"
        f"📅 Регистрация: {profile['reg_date']}"
    )

    send_profile_photo(message.chat.id, text)


@bot.message_handler(func=lambda message: message.text == "🧮 Калькулятор")
def calculator(message):
    bot.send_message(
        message.chat.id,
        f"🧮 Калькулятор\n\nКурс: 1 GOLD = {GOLD_RATE} ₽",
        reply_markup=get_calculator_keyboard()
    )


# ================== ОБРАБОТЧИК ВСЕХ INLINE КНОПОК ==================

@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    try:
        # Навигация
        if call.data == "back_to_menu":
            bot.delete_message(chat_id, message_id)
            bot.send_message(chat_id, "Главное меню:", reply_markup=get_main_menu())

        # Покупка
        elif call.data == "enter_purchase_amount":
            bot.delete_message(chat_id, message_id)
            msg = bot.send_message(
                chat_id,
                f"✏️ Введите количество GOLD\n"
                f"Мин: {MIN_PURCHASE}, Макс: {MAX_PURCHASE}"
            )
            user_data[user_id] = {'state': 'waiting_purchase_amount', 'msg_id': msg.message_id}

        # Калькулятор
        elif call.data == "calc_gold_to_rub":
            bot.delete_message(chat_id, message_id)
            msg = bot.send_message(chat_id, "🍯 Введите GOLD:")
            user_data[user_id] = {'state': 'waiting_gold_to_rub', 'msg_id': msg.message_id}

        elif call.data == "calc_rub_to_gold":
            bot.delete_message(chat_id, message_id)
            msg = bot.send_message(chat_id, "₽ Введите рубли:")
            user_data[user_id] = {'state': 'waiting_rub_to_gold', 'msg_id': msg.message_id}

        # Подтверждение оплаты
        elif call.data.startswith("paid_"):
            order_number = int(call.data.split("_")[1])
            handle_payment_confirmation(call, order_number)

        # Вывод средств
        elif call.data == "skin_placed":
            handle_skin_placed(call)

        # Профиль
        elif call.data == "refresh_profile":
            bot.delete_message(chat_id, message_id)

            # Создаем временный объект
            class FakeMessage:
                def __init__(self, chat, from_user):
                    self.chat = chat
                    self.from_user = from_user

            fake = FakeMessage(
                chat=type('obj', (object,), {'id': chat_id})(),
                from_user=type('obj', (object,), {'id': user_id})()
            )
            show_profile(fake)

        # История покупок
        elif call.data.startswith("history_purchases_"):
            page = int(call.data.split("_")[2])
            show_purchase_history(call, page)

        # История выводов
        elif call.data.startswith("history_withdrawals_"):
            page = int(call.data.split("_")[2])
            show_withdrawal_history(call, page)

        # Пагинация покупок
        elif call.data.startswith("prev_purchases_"):
            page = int(call.data.split("_")[2])
            show_purchase_history(call, page)

        elif call.data.startswith("next_purchases_"):
            page = int(call.data.split("_")[2])
            show_purchase_history(call, page)

        # Пагинация выводов
        elif call.data.startswith("prev_withdrawals_"):
            page = int(call.data.split("_")[2])
            show_withdrawal_history(call, page)

        elif call.data.startswith("next_withdrawals_"):
            page = int(call.data.split("_")[2])
            show_withdrawal_history(call, page)

        # АДМИНСКИЕ КНОПКИ - ПОКУПКИ
        elif call.data.startswith("admin_accept_purchase_"):
            order_number = int(call.data.split("_")[3])
            admin_accept_purchase(call, order_number)

        elif call.data.startswith("admin_reject_purchase_"):
            order_number = int(call.data.split("_")[3])
            admin_reject_purchase(call, order_number)

        # АДМИНСКИЕ КНОПКИ - ВЫВОДЫ
        elif call.data.startswith("admin_accept_withdrawal_"):
            order_number = int(call.data.split("_")[3])
            admin_accept_withdrawal(call, order_number)

        elif call.data.startswith("admin_reject_withdrawal_"):
            order_number = int(call.data.split("_")[3])
            admin_reject_withdrawal(call, order_number)

    except Exception as e:
        logger.error(f"Ошибка в callback_inline: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка")


# ================== ОБРАБОТЧИКИ ТЕКСТОВЫХ СООБЩЕНИЙ ==================

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    user_id = message.from_user.id

    if user_id in user_data:
        state = user_data[user_id].get('state')

        if state == 'waiting_purchase_amount':
            process_purchase_amount(message)
        elif state == 'waiting_withdrawal_amount':
            process_withdrawal_amount(message)
        elif state == 'waiting_gold_to_rub':
            process_gold_to_rub(message)
        elif state == 'waiting_rub_to_gold':
            process_rub_to_gold(message)


# ================== ПОКУПКИ ==================

def process_purchase_amount(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    try:
        amount = float(message.text.strip())

        if amount < MIN_PURCHASE:
            bot.send_message(chat_id, f"❌ Минимум {MIN_PURCHASE} GOLD")
            return

        if amount > MAX_PURCHASE:
            bot.send_message(chat_id, f"❌ Максимум {MAX_PURCHASE} GOLD")
            return

        amount = int(amount)
        rub_amount = amount * GOLD_RATE

        order_number = db.add_purchase_order(
            user_id,
            message.from_user.username or "NoUsername",
            amount,
            rub_amount
        )

        user_data[user_id] = {
            'state': 'waiting_payment',
            'order_number': order_number,
            'gold_amount': amount,
            'rub_amount': rub_amount
        }

        bot.send_message(
            chat_id,
            f"🧾 Заказ №{order_number}\n\n"
            f"Сумма: {amount} GOLD\n"
            f"К оплате: {rub_amount:.2f} ₽\n\n"
            f"💳 {CARD_NUMBER1} СБЕР\n"
            f"💳 {CARD_NUMBER2} Юмани\n"
            f"💳 {CARD_NUMBER3} Wb банк\n\n"
            f"После оплаты нажмите кнопку:",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("✅ Я оплатил", callback_data=f"paid_{order_number}")
            )
        )

        if 'msg_id' in user_data[user_id]:
            try:
                bot.delete_message(chat_id, user_data[user_id]['msg_id'])
            except:
                pass

        timer = threading.Timer(300, payment_timeout, args=[order_number, user_id, chat_id])
        timer.daemon = True
        timer.start()

        pending_orders[order_number] = {
            'user_id': user_id,
            'timer': timer,
            'chat_id': chat_id,
            'amount': amount,
            'rub_amount': rub_amount
        }

    except ValueError:
        bot.send_message(chat_id, "❌ Введите число")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        bot.send_message(chat_id, "❌ Ошибка")


def payment_timeout(order_number, user_id, chat_id):
    if order_number in pending_orders:
        db.update_purchase_status(order_number, 'Отменен (таймаут)', 'Нет')
        bot.send_message(chat_id, f"⏰ Время истекло. Заявка №{order_number} закрыта.")
        del pending_orders[order_number]
        if user_id in user_data:
            del user_data[user_id]


def handle_payment_confirmation(call, order_number):
    user_id = call.from_user.id

    if order_number not in pending_orders:
        bot.answer_callback_query(call.id, "❌ Заказ не найден")
        return

    if pending_orders[order_number]['user_id'] != user_id:
        bot.answer_callback_query(call.id, "❌ Это не ваш заказ")
        return

    pending_orders[order_number]['timer'].cancel()

    bot.edit_message_text(
        f"📤 Заказ №{order_number}\n\nПришлите фото чека:",
        call.message.chat.id,
        call.message.message_id
    )

    user_data[user_id] = {
        'state': 'waiting_receipt',
        'order_number': order_number
    }


def handle_receipt_photo(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id not in user_data or user_data[user_id].get('state') != 'waiting_receipt':
        return

    order_number = user_data[user_id]['order_number']
    file_id = message.photo[-1].file_id

    db.update_purchase_receipt(order_number, file_id)
    order_info = pending_orders.get(order_number, {})

    bot.send_message(
        message.chat.id,
        f"✅ Заявка №{order_number} принята!\n⏱️ Ожидайте проверки."
    )

    admin_text = (
        f"🔄 Новая оплата\n"
        f"👤 @{message.from_user.username}\n"
        f"📦 Заказ №{order_number}\n"
        f"💰 {order_info.get('rub_amount', 0):.2f} ₽\n"
        f"🍯 {order_info.get('amount', 0)} GOLD"
    )

    try:
        bot.send_photo(
            ADMIN_GROUP_ID,
            file_id,
            caption=admin_text,
            reply_markup=get_admin_purchase_keyboard(order_number)
        )
    except Exception as e:
        logger.error(f"Ошибка отправки фото админам: {e}")
        bot.send_message(
            ADMIN_GROUP_ID,
            admin_text,
            reply_markup=get_admin_purchase_keyboard(order_number)
        )

    del user_data[user_id]


# ================== ВЫВОДЫ ==================

def process_withdrawal_amount(message):
    """Обработка введенной суммы для вывода"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    logger.info(f"💰 Пользователь {user_id} ввел сумму для вывода: {message.text.strip()}")

    try:
        gold_amount = float(message.text.strip())

        if gold_amount <= 0:
            bot.send_message(chat_id, "❌ Введите положительное число")
            return

        # Проверяем баланс
        balance = db.get_user_balance(user_id)
        logger.info(f"💎 Баланс пользователя {user_id}: {balance} GOLD")

        if balance < gold_amount:
            bot.send_message(
                chat_id,
                f"❌ Недостаточно GOLD. Ваш баланс: {balance} GOLD"
            )
            return

        gold_amount = int(gold_amount)

        # Расчет в GOLD: сумма + 20% + 0.04 GOLD
        commission_gold = gold_amount /(1-WITHDRAWAL_COMMISSION) - gold_amount
        total_gold = gold_amount + commission_gold + FIXED_FEE
        total_rub = total_gold * GOLD_RATE

        logger.info(
            f"📊 Расчет для {user_id}: {gold_amount} GOLD -> комиссия {commission_gold:.2f} GOLD, итого {total_gold:.2f} GOLD")

        user_data[user_id] = {
            'state': 'waiting_skin_confirmation',
            'gold_amount': gold_amount,
            'commission_gold': commission_gold,
            'total_gold': total_gold,
            'total_rub': total_rub
        }

        text = (
            f"🍯 Вывод {gold_amount} GOLD\n\n"
            f"📊 Расчет в GOLD:\n"
            f"• Сумма вывода: {gold_amount} GOLD\n\n"
            #"f"• Комиссия 20%: +{commission_gold:.2f} GOLD\n"
            #f"• Фикс. комиссия: +{FIXED_FEE} GOLD\n"
            #f"• ИТОГО к получению: {total_gold:.2f} GOLD\n\n"
            f"📌 Инструкция:\n"
            f"1. Выставьте скин на торговой площадке\n"
            f"2. Установите цену: {total_gold:.2f} GOLD\n"
            f"3. Сделайте скриншот выставленного скина\n"
            f"4. Нажмите кнопку '💎 Скин выставлен'\n"
            f"5. Отправьте фото скина"
        )
        # Отправляем сообщение с фото скина-примера
        send_withdrawal_instruction_with_photo(chat_id, text, total_gold, user_id)

        logger.info(f"✅ Сообщение о выводе отправлено пользователю {user_id}")

    except ValueError:
        bot.send_message(chat_id, "❌ Введите число")
    except Exception as e:
        logger.error(f"❌ Ошибка в process_withdrawal_amount: {e}")
        bot.send_message(chat_id, "❌ Произошла ошибка")


def send_withdrawal_instruction_with_photo(chat_id, text, total_gold, user_id):
    """Отправка инструкции по выводу с фото скина-примера"""

    # Пытаемся отправить с фото скина-примера по file_id
    if image_manager.skin_example_file_id:
        try:
            # Проверяем, что file_id не пустой и является строкой
            if isinstance(image_manager.skin_example_file_id, str) and len(image_manager.skin_example_file_id) > 10:
                sent_msg = bot.send_photo(
                    chat_id,
                    image_manager.skin_example_file_id,
                    caption=text,
                    reply_markup=get_withdrawal_keyboard()
                )
                user_data[user_id]['message_id'] = sent_msg.message_id
                logger.info(
                    f"✅ Отправлено сообщение с фото скина-примера (file_id: {image_manager.skin_example_file_id[:20]}...)")
                return True
        except Exception as e:
            logger.error(f"Ошибка отправки skin по file_id: {e}")
            # Не сбрасываем file_id, просто логируем ошибку
    else:
        logger.warning("❌ skin_example_file_id не установлен в конфиге")

    # Если не получилось отправить по file_id - отправляем без фото
    logger.info("⚠️ Отправка сообщения без фото (нет рабочего file_id)")
    sent_msg = bot.send_message(
        chat_id,
        text,
        reply_markup=get_withdrawal_keyboard()
    )
    user_data[user_id]['message_id'] = sent_msg.message_id
    return False

    # Если ничего не сработало - отправляем без фото
    sent_msg = bot.send_message(
        chat_id,
        text,
        reply_markup=get_withdrawal_keyboard()
    )
    user_data[user_id]['message_id'] = sent_msg.message_id
    logger.info(f"✅ Отправлено сообщение без фото (текст)")

def handle_skin_placed(call):
    """Обработка нажатия кнопки 'Скин выставлен'"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    logger.info(f"💎 Пользователь {user_id} нажал кнопку 'Скин выставлен'")

    if user_id not in user_data or user_data[user_id].get('state') != 'waiting_skin_confirmation':
        bot.answer_callback_query(call.id, "❌ Сессия истекла. Начните вывод заново.")
        return

    data = user_data[user_id]

    # Меняем состояние на ожидание фото скина
    user_data[user_id]['state'] = 'waiting_skin_photo'
    logger.info(f"📸 Пользователь {user_id} переведен в режим ожидания фото скина")

    # Текст для нового сообщения
    text = (
        f"💎 Заявка на вывод {data['gold_amount']} GOLD\n\n"
        f"📊 Расчет:\n"
        f"• Сумма: {data['gold_amount']} GOLD\n"
        f"• Комиссия 20%: +{data['commission_gold']:.2f} GOLD\n"
        f"• Фикс. комиссия: +{FIXED_FEE} GOLD\n"
        f"• Итого к получению: {data['total_gold']:.2f} GOLD\n\n"
        f"📸 Теперь отправьте фото выставленного скина\n"
        f"(скриншот с ценой {data['total_gold']:.2f} GOLD)"
    )

    # Отправляем НОВОЕ сообщение
    bot.send_message(
        chat_id,
        text
    )

    # Удаляем старое сообщение с кнопкой
    try:
        bot.delete_message(chat_id, call.message.message_id)
        logger.info(f"✅ Старое сообщение удалено")
    except Exception as e:
        logger.error(f"❌ Не удалось удалить старое сообщение: {e}")

    bot.answer_callback_query(call.id, "✅ Ожидаем фото скина")


# ================== ГЛАВНЫЙ ОБРАБОТЧИК ФОТО ==================

@bot.message_handler(content_types=['photo'])
def handle_all_photos(message):
    """Главный обработчик всех фото"""
    user_id = message.from_user.id
    logger.info(f"📸 Получено фото от пользователя {user_id}")

    # 1. Сначала проверяем режим получения file_id
    if user_id in get_id_mode and get_id_mode[user_id]:
        logger.info("🔄 Режим получения file_id")
        handle_file_id_request(message)
        return

    # 2. Проверяем, ожидаем ли мы фото скина для вывода
    if user_id in user_data and user_data[user_id].get('state') == 'waiting_skin_photo':
        logger.info("💎 Обработка фото скина для вывода")
        handle_skin_photo(message)
        return

    # 3. Проверяем, ожидаем ли мы фото чека для покупки
    if user_id in user_data and user_data[user_id].get('state') == 'waiting_receipt':
        logger.info("🧾 Обработка фото чека для покупки")
        handle_receipt_photo(message)
        return

    # 4. Если ничего не подошло
    logger.warning(f"❌ Неожиданное фото от пользователя {user_id}")
    bot.send_message(
        message.chat.id,
        "❌ Сейчас не требуется отправлять фото. Используйте /get_id если хотите получить File ID."
    )


def handle_skin_photo(message):
    """Обработка фото скина при выводе"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Получаем данные пользователя
    data = user_data.get(user_id)
    if not data:
        logger.error(f"❌ Нет данных для пользователя {user_id}")
        bot.send_message(chat_id, "❌ Ошибка: сессия истекла. Начните вывод заново.")
        return

    file_id = message.photo[-1].file_id
    logger.info(f"📸 Получено фото скина от {user_id}, file_id: {file_id}")

    try:
        # Создаем заявку на вывод в БД
        username = message.from_user.username or "NoUsername"
        order_number = db.add_withdrawal_order(
            user_id,
            username,
            data['gold_amount'],
            data['total_rub']
        )

        logger.info(f"✅ Заявка на вывод #{order_number} создана в БД")

        # Обновляем баланс (списываем GOLD)
        new_balance = db.update_gold_balance(user_id, data['gold_amount'], 'subtract')
        logger.info(f"💰 Баланс пользователя {user_id} обновлен: {new_balance} GOLD")

        # Отправляем подтверждение пользователю
        success_text = (
            f"✅ Заявка на вывод №{order_number} создана!\n\n"
            f"🍯 Сумма вывода: {data['gold_amount']} GOLD\n"
            f"📊 Скин выставлен на: {data['total_gold']:.2f} GOLD\n\n"
            f"⏱️ Ожидайте подтверждения администратором.\n"
            f"💎 Новый баланс: {new_balance} GOLD"
        )

        bot.send_message(
            chat_id,
            success_text
        )
        logger.info(f"✅ Подтверждение отправлено пользователю {user_id}")

        # Отправляем уведомление админам с фото скина
        admin_text = (
            f"🔄 НОВАЯ ЗАЯВКА НА ВЫВОД\n"
            f"👤 @{message.from_user.username}\n"
            f"🆔 {user_id}\n"
            f"📦 Заказ №{order_number}\n\n"
            f"📊 Расчет:\n"
            f"• Запрошено: {data['gold_amount']} GOLD\n"
            f"• Комиссия 20%: +{data['commission_gold']:.2f} GOLD\n"
            f"• Фикс: +{FIXED_FEE} GOLD\n"
            f"• Скин на сумму: {data['total_gold']:.2f} GOLD\n"
        )

        # Отправляем фото админам
        try:
            bot.send_photo(
                ADMIN_GROUP_ID,
                file_id,
                caption=admin_text,
                reply_markup=get_admin_withdrawal_keyboard(order_number)
            )
            logger.info(f"✅ Уведомление о выводе #{order_number} отправлено админам")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки фото админам: {e}")
            # Если не получилось с фото, отправляем только текст
            try:
                bot.send_message(
                    ADMIN_GROUP_ID,
                    admin_text + f"\n\n❌ Фото не загрузилось, но заявка создана.",
                    reply_markup=get_admin_withdrawal_keyboard(order_number)
                )
                logger.info(f"✅ Текстовое уведомление админам отправлено")
            except Exception as e2:
                logger.error(f"❌ Даже текст не отправился: {e2}")

        # Очищаем данные пользователя
        del user_data[user_id]
        logger.info(f"✅ Данные пользователя {user_id} очищены")

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке вывода: {e}")
        bot.send_message(
            chat_id,
            "❌ Произошла ошибка при создании заявки. Попробуйте позже."
        )


def handle_file_id_request(message):
    """Обработка запроса на получение file_id"""
    user_id = message.from_user.id
    file_id = message.photo[-1].file_id

    file_info = bot.get_file(file_id)
    file_size = file_info.file_size

    response = (
        f"📸 File ID получен!\n\n"
        f"{file_id}\n\n"
        f"📊 Информация:\n"
        f"• Размер: {file_size // 1024} КБ\n"
        f"• Разрешение: {message.photo[-1].width}x{message.photo[-1].height}\n\n"
        f"📌 Как использовать:\n"
        f"Скопируйте этот File ID в config.py:\n"
        f"WELCOME_IMAGE_FILE_ID = \"{file_id}\"\n"
        f"PROFILE_IMAGE_FILE_ID = \"{file_id}\"\n"
        f"SKIN_EXAMPLE_FILE_ID = \"{file_id}\"\n\n"
        f"🔄 Продолжайте отправлять фото или используйте /stop_get_id"
    )

    bot.send_message(
        message.chat.id,
        response
    )

    logger.info(f"📸 User {user_id} got file_id: {file_id}")


# ================== АДМИНСКИЕ ФУНКЦИИ (ПОКУПКИ) ==================

def admin_accept_purchase(call, order_number):
    """Админ подтверждает оплату покупки"""
    logger.info(f"✅ Админ подтверждает оплату покупки #{order_number}")

    order_info = pending_orders.get(order_number)

    if order_info:
        user_id = order_info['user_id']
        gold_amount = order_info['amount']
    else:
        order = db.get_purchase_order(order_number)
        if not order:
            bot.answer_callback_query(call.id, "❌ Заказ не найден")
            return
        user_id = order['user_id']
        gold_amount = order['gold_amount']

    # Начисляем GOLD
    new_balance = db.update_gold_balance(user_id, gold_amount, 'add')
    db.update_purchase_status(order_number, 'Оплачен', 'Да')

    # Отправляем уведомление пользователю
    try:
        bot.send_message(
            user_id,
            f"✅ Оплата по заказу №{order_number} принята!\n"
            f"💰 Зачислено: {gold_amount} GOLD\n"
            f"💎 Баланс: {new_balance} GOLD"
        )
    except:
        pass

    # Обновляем сообщение админа
    try:
        bot.edit_message_caption(
            f"✅ ПЛАТЕЖ ПРИНЯТ\n\n{call.message.caption}",
            call.message.chat.id,
            call.message.message_id
        )
    except:
        bot.send_message(
            call.message.chat.id,
            f"✅ ПЛАТЕЖ #{order_number} ПРИНЯТ"
        )
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass

    if order_number in pending_orders:
        del pending_orders[order_number]

    bot.answer_callback_query(call.id, "✅ Принято")


def admin_reject_purchase(call, order_number):
    """Админ отклоняет оплату покупки"""
    logger.info(f"❌ Админ отклоняет оплату покупки #{order_number}")

    order_info = pending_orders.get(order_number)

    if order_info:
        user_id = order_info['user_id']
    else:
        order = db.get_purchase_order(order_number)
        if order:
            user_id = order['user_id']
        else:
            bot.answer_callback_query(call.id, "❌ Заказ не найден")
            return

    db.update_purchase_status(order_number, 'Отклонен', 'Да')

    # Отправляем уведомление пользователю
    try:
        bot.send_message(
            user_id,
            f"❌ Отказано в оплате по заказу №{order_number}\n\n"
            f"Платеж не прошел проверку. Свяжитесь с поддержкой."
        )
    except:
        pass

    # Обновляем сообщение админа
    try:
        bot.edit_message_caption(
            f"❌ ПЛАТЕЖ ОТКЛОНЕН\n\n{call.message.caption}",
            call.message.chat.id,
            call.message.message_id
        )
    except:
        bot.send_message(
            call.message.chat.id,
            f"❌ ПЛАТЕЖ #{order_number} ОТКЛОНЕН"
        )
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass

    if order_number in pending_orders:
        del pending_orders[order_number]

    bot.answer_callback_query(call.id, "❌ Отклонено")


# ================== АДМИНСКИЕ ФУНКЦИИ (ВЫВОДЫ) ==================

def admin_accept_withdrawal(call, order_number):
    """Админ подтверждает вывод"""
    logger.info(f"✅ Админ подтверждает вывод #{order_number}")

    order = db.get_withdrawal_order(order_number)
    if not order:
        bot.answer_callback_query(call.id, "❌ Заказ не найден")
        return

    # Обновляем статус в БД
    db.update_withdrawal_status(order_number, 'Подтвержден', 'Да')

    # Отправляем уведомление пользователю
    try:
        bot.send_message(
            order['user_id'],
            f"✅ Вывод №{order_number} подтверждён!"
        )
        logger.info(f"✅ Уведомление отправлено пользователю {order['user_id']}")
    except Exception as e:
        logger.error(f"❌ Не удалось отправить уведомление пользователю: {e}")

    # Обновляем сообщение админа
    try:
        bot.edit_message_text(
            f"✅ ВЫВОД ПОДТВЕРЖДЕН\n\n{call.message.caption if call.message.caption else call.message.text}",
            call.message.chat.id,
            call.message.message_id
        )
    except:
        bot.send_message(
            call.message.chat.id,
            f"✅ ВЫВОД #{order_number} ПОДТВЕРЖДЕН\n\n"
            f"👤 Клиент: @{order['username']}\n"
        )
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass

    bot.answer_callback_query(call.id, "✅ Вывод подтвержден")


def admin_reject_withdrawal(call, order_number):
    """Админ отклоняет вывод"""
    logger.info(f"❌ Админ отклоняет вывод #{order_number}")

    order = db.get_withdrawal_order(order_number)
    if not order:
        bot.answer_callback_query(call.id, "❌ Заказ не найден")
        return

    # Возвращаем GOLD пользователю
    new_balance = db.update_gold_balance(order['user_id'], order['gold_amount'], 'add')
    # Обновляем статус
    db.update_withdrawal_status(order_number, 'Отклонен', 'Да')

    # Отправляем уведомление пользователю
    try:
        bot.send_message(
            order['user_id'],
            f"❌ Вывод №{order_number} отклонён\n\n"
            f"💰 GOLD в количестве {order['gold_amount']} возвращён на баланс.\n"
            f"💎 Текущий баланс: {new_balance} GOLD"
        )
        logger.info(f"✅ Уведомление об отклонении отправлено пользователю {order['user_id']}")
    except Exception as e:
        logger.error(f"❌ Не удалось отправить уведомление пользователю: {e}")

    # Обновляем сообщение админа
    try:
        bot.edit_message_text(
            f"❌ ВЫВОД ОТКЛОНЕН\n\n{call.message.caption if call.message.caption else call.message.text}",
            call.message.chat.id,
            call.message.message_id
        )
    except:
        bot.send_message(
            call.message.chat.id,
            f"❌ ВЫВОД #{order_number} ОТКЛОНЕН\n\n"
            f"👤 Клиент: @{order['username']}\n"
        )
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass

    bot.answer_callback_query(call.id, "❌ Вывод отклонен")


# ================== КАЛЬКУЛЯТОР ==================

def process_gold_to_rub(message):
    try:
        gold = float(message.text.strip())
        bot.send_message(
            message.chat.id,
            f"🍯 {gold} GOLD = ₽ {gold * GOLD_RATE:.2f}",
            reply_markup=get_calculator_keyboard()
        )
        del user_data[message.from_user.id]
    except:
        bot.send_message(message.chat.id, "❌ Введите число")


def process_rub_to_gold(message):
    try:
        rub = float(message.text.strip())
        bot.send_message(
            message.chat.id,
            f"₽ {rub} = 🍯 {rub / GOLD_RATE:.2f} GOLD",
            reply_markup=get_calculator_keyboard()
        )
        del user_data[message.from_user.id]
    except:
        bot.send_message(message.chat.id, "❌ Введите число")


# ================== ИСТОРИЯ ==================

def show_purchase_history(call, page=1):
    user_id = call.from_user.id
    per_page = 5

    history = db.get_user_purchases(user_id, per_page, (page - 1) * per_page)

    if not history and page == 1:
        bot.send_message(
            call.message.chat.id,
            "📜 История покупок пуста",
            reply_markup=get_profile_keyboard()
        )
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        return

    text = f"📜 История покупок (стр.{page})\n\n"
    for h in history:
        if h['status'] == 'Оплачен':
            emoji = "✅"
        elif h['status'] == 'Ожидает проверки':
            emoji = "⏳"
        else:
            emoji = "❌"

        text += f"{emoji} №{h['order_number']}\n"
        text += f"   🍯 {h['gold_amount']} GOLD = ₽ {h['rub_amount']}\n"
        text += f"   Статус: {h['status']}\n\n"

    # Кнопки пагинации
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    buttons = []

    if page > 1:
        buttons.append(types.InlineKeyboardButton("◀️", callback_data=f"prev_purchases_{page - 1}"))

    buttons.append(types.InlineKeyboardButton("◀️ Назад", callback_data="refresh_profile"))

    # Проверяем, есть ли следующая страница
    next_page = db.get_user_purchases(user_id, per_page, page * per_page)
    if next_page:
        buttons.append(types.InlineKeyboardButton("▶️", callback_data=f"next_purchases_{page + 1}"))

    keyboard.add(*buttons)

    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
    except:
        bot.send_message(
            call.message.chat.id,
            text,
            reply_markup=keyboard
        )


def show_withdrawal_history(call, page=1):
    user_id = call.from_user.id
    per_page = 5

    history = db.get_user_withdrawals(user_id, per_page, (page - 1) * per_page)

    if not history and page == 1:
        bot.send_message(
            call.message.chat.id,
            "📤 История выводов пуста",
            reply_markup=get_profile_keyboard()
        )
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        return

    text = f"📤 История выводов (стр.{page})\n\n"
    for h in history:
        if h['status'] == 'Подтвержден':
            emoji = "✅"
        elif h['status'] == 'Ожидает проверки':
            emoji = "⏳"
        else:
            emoji = "❌"

        text += f"{emoji} №{h['order_number']}\n"
        text += f"   🍯 {h['gold_amount']} GOLD = ₽ {h['rub_amount']}\n"
        text += f"   Статус: {h['status']}\n\n"

    # Кнопки пагинации
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    buttons = []

    if page > 1:
        buttons.append(types.InlineKeyboardButton("◀️", callback_data=f"prev_withdrawals_{page - 1}"))

    buttons.append(types.InlineKeyboardButton("◀️ Назад", callback_data="refresh_profile"))

    # Проверяем, есть ли следующая страница
    next_page = db.get_user_withdrawals(user_id, per_page, page * per_page)
    if next_page:
        buttons.append(types.InlineKeyboardButton("▶️", callback_data=f"next_withdrawals_{page + 1}"))

    keyboard.add(*buttons)

    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
    except:
        bot.send_message(
            call.message.chat.id,
            text,
            reply_markup=keyboard
        )

ADMIN_IDS = [8214136791, 1441402891]

@bot.message_handler(commands=['get_db'])
def get_db_file(message):
    user_id = message.from_user.id
    print(f"DEBUG: Команда /get_db от пользователя {user_id}")  # Это будет видно в логах Railway

    # Проверка прав
    if user_id in ADMIN_IDS:
        try:
            # Берем путь прямо из объекта базы данных
            db_path = db.db_file

            if os.path.exists(db_path):
                with open(db_path, 'rb') as f:
                    bot.send_document(message.chat.id, f, caption=f"✅ База найдена по пути: {db_path}")
            else:
                bot.reply_to(message, f"❓ Файл {db_path} физически не найден на сервере.")

        except Exception as e:
            bot.reply_to(message, f"⚠️ Произошла ошибка при чтении: {e}")

    else:
        # ЭТО БУДЕТ ПИСАТЬ ВСЕМ ОСТАЛЬНЫМ
        bot.reply_to(message, "⛔ Эта функция доступна только админам.")

# ================== ЗАПУСК ==================

if __name__ == "__main__":
    logger.info("🚀 Бот запущен...")

    # Проверка наличия изображений
    if os.path.exists(WELCOME_IMAGE_PATH) and os.path.exists(PROFILE_IMAGE_PATH):
        logger.info("✅ Файлы изображений найдены в папке images")
    else:
        logger.warning("⚠️ Файлы изображений не найдены, бот будет работать без картинок")

    # Запуск
    try:
        bot.infinity_polling()
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
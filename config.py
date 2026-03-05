"""
import os

from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = "8788647589:AAFIiUbd8OBAsAixs6k7JvRJdjAERRxqXO8"

# Google Sheets IDs
SHEET_PURCHASES = "1J_GYPtdHQKgRX1znMgTKtuK5HHKUHpDS2rM0KW9twxs"  # История покупок GOLD
SHEET_WITHDRAWALS = "1BGFdR9oHRkt0FDUiqRvqTilqiBxZz4bD7r8gm00JLG4"  # История выводов GOLD
SHEET_PROFILES = "1LzJBBTOFqurPYlZlLLjmE4_BRz63f4uSQxwRPmFW0Nk"  # Профили пользователей

# Admin group/channel ID (где будут получать уведомления админы)
ADMIN_GROUP_ID = -5275767277  # Замените на ваш ID группы

# Currency rate
GOLD_RATE = 0.73  # 1 GOLD = 0.75 RUB

# Payment details
CARD_NUMBER1 = "2202206868825162"
CARD_NUMBER2 = "5599002131542013"
CARD_NUMBER3 = "89085548604"

# Path to images
WELCOME_IMAGE_PATH  = "images/welcome.jpg"
PROFILE_IMAGE_PATH  = "images/profile.jpg"
SKIN_EXAMPLE_FILE_ID  = "images/profile.jpg"

WELCOME_IMAGE_FILE_ID = "AgACAgIAAxkBAAICX2moVRh2JdukVdH6QgJX7C387HzvAAJnFmsbHVVISatYTnq91cwqAQADAgADeQADOgQ"
PROFILE_IMAGE_FILE_ID = "AgACAgIAAxkBAAICo2mpcgZczfaqng4IQ8mcPTh4rrAbAAKiFmsbHVVQST_ETI9-tf0xAQADAgADeQADOgQ"
SKIN_EXAMPLE_FILE_ID = "AgACAgIAAxkBAAICY2moVTUoU7flc9GQpKzlFo5jUwc9AAJrFmsbHVVISbLGTNPCmJQhAQADAgADeQADOgQ"  # Новое фото примера скина
"""

import os
from dotenv import load_dotenv

# Загружаем .env только на локальном компьютере
load_dotenv()

# Telegram Bot Token (берем из переменных окружения)
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в переменных окружения!")

# Google Sheets IDs (можно оставить, они не секретные)
SHEET_PURCHASES = os.getenv('SHEET_PURCHASES', "1J_GYPtdHQKgRX1znMgTKtuK5HHKUHpDS2rM0KW9twxs")
SHEET_WITHDRAWALS = os.getenv('SHEET_WITHDRAWALS', "1BGFdR9oHRkt0FDUiqRvqTilqiBxZz4bD7r8gm00JLG4")
SHEET_PROFILES = os.getenv('SHEET_PROFILES', "1LzJBBTOFqurPYlZlLLjmE4_BRz63f4uSQxwRPmFW0Nk")

# Admin group ID (берем из переменных окружения)
ADMIN_GROUP_ID = int(os.getenv('ADMIN_GROUP_ID', '-5275767277'))

# Currency rate
GOLD_RATE = float(os.getenv('GOLD_RATE', '0.73'))

# Payment details (номера карт)
CARD_NUMBER1 = os.getenv('CARD_NUMBER1', "2202206868825162")
CARD_NUMBER2 = os.getenv('CARD_NUMBER2', "5599002131542013")
CARD_NUMBER3 = os.getenv('CARD_NUMBER3', "89085548604")

# Path to images (пути к файлам - не секретно)
WELCOME_IMAGE_PATH = "images/welcome.jpg"
PROFILE_IMAGE_PATH = "images/profile.jpg"
SKIN_EXAMPLE_PATH = "images/skin_example.jpg"  # ИСПРАВЛЕНО: было SKIN_EXAMPLE_FILE_ID

# File IDs для изображений (берем из переменных окружения)
WELCOME_IMAGE_FILE_ID = os.getenv('WELCOME_IMAGE_FILE_ID')
PROFILE_IMAGE_FILE_ID = os.getenv('PROFILE_IMAGE_FILE_ID')
SKIN_EXAMPLE_FILE_ID = os.getenv('SKIN_EXAMPLE_FILE_ID')
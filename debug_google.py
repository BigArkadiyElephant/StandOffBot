import gspread
import os

print("1️⃣ Проверяем файл credentials.json")
path = "credentials.json"
if os.path.exists(path):
    print("   ✅ Файл найден")
else:
    print("   ❌ Файл не найден")
    exit()

print("\n2️⃣ Подключаемся к Google")
try:
    gc = gspread.service_account(filename=path)
    print("   ✅ Подключение успешно")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")
    exit()

print("\n3️⃣ Открываем таблицу по ID")
SHEET_ID = "1molr71XhEE7HC1jfS1xt1CWwAqKxUdfshLwbh0W_5VI"
try:
    sheet = gc.open_by_key(SHEET_ID)
    print(f"   ✅ Таблица открыта: {sheet.title}")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")
    print("\n   👉 Возможные причины:")
    print("   1. Неправильный ID таблицы")
    print("   2. Вы не дали доступ сервисному аккаунту")
    print("   3. Таблица удалена")
    exit()

print("\n4️⃣ Проверяем листы")
expected_sheets = ["Профили", "Покупки", "Выводы"]
existing_sheets = [ws.title for ws in sheet.worksheets()]
print(f"   Существующие листы: {existing_sheets}")

for sheet_name in expected_sheets:
    if sheet_name in existing_sheets:
        print(f"   ✅ Лист '{sheet_name}' найден")
    else:
        print(f"   ❌ Лист '{sheet_name}' НЕ найден")

print("\n🎉 Проверка завершена!")
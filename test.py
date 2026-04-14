import os

# Проверяем, есть ли файл
path = "credentials.json"
if os.path.exists(path):
    print(f"✅ Файл найден: {path}")
    print(f"Размер: {os.path.getsize(path)} байт")

    # Показываем первые 100 символов файла
    with open(path, 'r') as f:
        content = f.read(100)
        print(f"Начало файла: {content[:50]}...")
else:
    print(f"❌ Файл НЕ найден: {path}")
    print(f"Текущая папка: {os.getcwd()}")
    print("Файлы в папке:", os.listdir())
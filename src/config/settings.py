import os
from dotenv import load_dotenv

load_dotenv()  
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN не установлен в .env!")

BASE_URL = os.getenv(
    'BASE_URL',
    'https://oksei.ru/studentu/raspisanie_uchebnykh_zanyatij'
)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise ValueError("ADMIN_PASSWORD не установлен в .env! Добавьте строку ADMIN_PASSWORD=ваш_пароль")
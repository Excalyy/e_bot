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
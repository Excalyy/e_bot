from telebot.async_telebot import AsyncTeleBot
from src.config.settings import TOKEN

assert TOKEN is not None

bot = AsyncTeleBot(TOKEN)

user_groups: dict[int, str] = {}
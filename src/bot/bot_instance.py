import asyncio
from telebot.async_telebot import AsyncTeleBot
from src.config.settings import TOKEN
from src.database.db import db
from src.bot.core import bot, user_groups
from src.bot.preload import preload_all_schedules
from src.utils.logger import log

# Импортируем хендлеры — они зарегистрируются при импорте
import src.bot.handlers

assert TOKEN is not None  # Для PyLance

async def run_bot():
    log.info("=" * 50)
    log.info("🚀 ЗАПУСК БОТА РАСПИСАНИЯ ОКЭИ")
    log.info("=" * 50)
    
    await db.connect()
    await preload_all_schedules()
    await db.cleanup_old_data(days_old=1)
    
    log.info("🤖 Бот запущен и готов к работе!")
    log.info("Для остановки нажмите Ctrl+C")
    log.info("=" * 50)
    
    try:
        await bot.polling(none_stop=False, interval=0, timeout=20)
    except KeyboardInterrupt:
        log.info("⏳ Получен Ctrl+C — останавливаем бота...")
    except Exception as e:
        log.error(f"💥 Неожиданная ошибка при polling: {e}")
    finally:
        log.info("🔄 Закрываем соединение с базой данных...")
        await db.close()
        log.info("👋 Бот корректно остановлен. До свидания!")

if __name__ == "__main__":
    asyncio.run(run_bot())
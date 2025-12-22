from telebot.types import Message
from src.bot.core import bot, user_groups
from src.bot.preload import preload_all_schedules
from src.bot.constants import GROUPS_BY_COURSE, DAYS_MAPPING
from src.bot.keyboards import (
    create_courses_keyboard,
    create_groups_keyboard,
    create_schedule_keyboard,
)
from src.database.db import db
from src.utils.formatting import format_daily_schedule, format_weekly_schedule

# === /start ===
@bot.message_handler(commands=['start'])
async def send_welcome(message: Message):
    user_id = message.from_user.id
    saved_group = await db.get_user_group(user_id)
    
    username = message.from_user.username or message.from_user.first_name or "друг"
    
    if saved_group:
        await bot.send_message(
            message.chat.id,
            f"С возвращением, {username}! Ваша группа: {saved_group}\nВыберите день:",
            reply_markup=create_schedule_keyboard()
        )
    else:
        await bot.send_message(
            message.chat.id,
            f"Привет, {username}! Выбери свой курс:",
            reply_markup=create_courses_keyboard()
        )

# === Выбор курса ===
@bot.message_handler(func=lambda m: m.text is not None and m.text in GROUPS_BY_COURSE.keys())
async def handle_course_selection(message: Message):
    text = message.text
    if text is None:  # Дополнительная защита (хотя не должна сработать)
        return
    course = text  # Теперь PyLance 100% знает, что это str
    await bot.send_message(
        message.chat.id,
        f"Выбран курс: {course}. Теперь выбери группу:",
        reply_markup=create_groups_keyboard(course)
    )

# === Назад к курсам ===
@bot.message_handler(func=lambda m: m.text == "Назад к курсам")
async def handle_back_to_courses(message: Message):
    await bot.send_message(
        message.chat.id,
        "Выбери свой курс:",
        reply_markup=create_courses_keyboard()
    )

# === Выбор группы ===
@bot.message_handler(func=lambda m: m.text is not None and any(m.text in groups for groups in GROUPS_BY_COURSE.values()))
async def handle_group_selection(message: Message):
    text = message.text
    if text is None:
        return
    group = text.strip()  # Теперь strip точно на str
    
    user_id = message.from_user.id
    user_groups[user_id] = group
    await db.save_user_preference(user_id, group)
    
    await bot.send_message(
        message.chat.id,
        f"Выбрана группа: {group}. Теперь выбери день:",
        reply_markup=create_schedule_keyboard()
    )

# === Расписание ===
@bot.message_handler(func=lambda m: m.text is not None and m.text in DAYS_MAPPING.keys())
async def send_schedule(message: Message):
    text = message.text
    if text is None:
        return
    day_text = text.strip()
    day_key = DAYS_MAPPING[day_text]
    
    user_id = message.from_user.id
    
    if user_id not in user_groups:
        await bot.send_message(message.chat.id, "Сначала выбери группу:", reply_markup=create_courses_keyboard())
        return
    
    if day_key == "change_group":
        await bot.send_message(message.chat.id, "Выбери новый курс:", reply_markup=create_courses_keyboard())
        return
    
    group = user_groups[user_id]
    schedule_data = await db.get_schedule(group)
    
    if not schedule_data:
        await bot.send_message(message.chat.id, f"Расписание для группы {group} не найдено.\nПопробуйте позже.")
        return
    
    await db.log_request(user_id, group, day_text)
    
    if day_key == "week":
        response = format_weekly_schedule(schedule_data, group)
    else:
        response = format_daily_schedule(schedule_data, day_key, day_text, group)
    
    await bot.send_message(message.chat.id, response)

# === Админ-команды (без изменений, они не используют message.text) ===
@bot.message_handler(commands=['stats'])
async def send_stats(message: Message):
    stats = await db.get_statistics()
    response = "📊 **Статистика бота:**\n\n"
    response += f"👥 Всего пользователей: {stats.get('total_users', 0)}\n"
    response += f"📨 Всего запросов: {stats.get('total_requests', 0)}\n"
    popular = stats.get('popular_groups', [])
    if popular:
        response += "\n🏆 **Популярные группы:**\n"
        for g in popular:
            response += f"  • {g['_id']}: {g['count']} запросов\n"
    await bot.send_message(message.chat.id, response, parse_mode='Markdown')

@bot.message_handler(commands=['clearcache'])
async def clear_cache(message: Message):
    await db.cleanup_old_data(days_old=1)
    await bot.send_message(message.chat.id, "✅ Кэш успешно очищен!")

@bot.message_handler(commands=['dbinfo'])
async def db_info(message: Message):
    info = await db.get_database_info()
    response = "🗃️ **Информация о базе данных:**\n\n"
    response += f"📁 Путь: `{info.get('database_path', 'data/schedule_bot.db')}`\n\n"
    tables = info.get('tables', {})
    if tables:
        response += "**Таблицы:**\n"
        for table, count in tables.items():
            response += f"  • {table}: {count} записей\n"
    await bot.send_message(message.chat.id, response, parse_mode='Markdown')

@bot.message_handler(commands=['update'])
async def update_schedules(message: Message):
    await bot.send_message(message.chat.id, "🔄 Начинаем обновление всех расписаний...")
    count = await preload_all_schedules()
    await bot.send_message(message.chat.id, f"✅ Обновление завершено! Загружено расписаний: {count}")

@bot.message_handler(commands=['help', 'помощь'])
async def send_help(message: Message):
    help_text = """
🤖 **Команды бота**

/start — Начать работу
/help — Эта справка
/stats — Статистика (админ)
/dbinfo — Инфо о БД (админ)
/clearcache — Очистить кэш (админ)
/update — Обновить расписания (админ)

Выбирайте кнопки — всё просто!
    """
    await bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

# === Ловец остальных сообщений ===
@bot.message_handler(func=lambda m: True)
async def handle_other(message: Message):
    user_id = message.from_user.id
    if user_id in user_groups:
        await bot.send_message(
            message.chat.id,
            "Используйте кнопки ниже для выбора дня:",
            reply_markup=create_schedule_keyboard()
        )
    else:
        await bot.send_message(
            message.chat.id,
            "Сначала выберите свой курс:",
            reply_markup=create_courses_keyboard()
        )
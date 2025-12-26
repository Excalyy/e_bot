import re
from telebot.types import Message
from src.bot.core import bot, user_groups
from src.bot.preload import preload_all_schedules
from src.bot.constants import GROUPS_BY_COURSE, DAYS_MAPPING
from src.bot.keyboards import (
    create_courses_keyboard,
    create_groups_keyboard,
    create_schedule_keyboard,
    create_main_menu_keyboard,
    create_back_to_main_keyboard,
)
from src.database.db import db
from src.utils.formatting import format_daily_schedule, format_weekly_schedule

# Состояния пользователей (режим поиска преподавателя)
search_mode: dict[int, bool] = {}


# === /start — главное меню ===
@bot.message_handler(commands=['start'])
async def send_welcome(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or "друг"
    
    search_mode[user_id] = False  # выключаем режим поиска
    
    await bot.send_message(
        message.chat.id,
        f"👋 Привет, {username}!\n\n"
        "Я бот с расписанием. Выберите, что хотите сделать:",
        reply_markup=create_main_menu_keyboard()
    )


# === Универсальная кнопка "🏠 Главное меню" (надёжная) ===
@bot.message_handler(func=lambda m: m.text and m.text.strip() == "🏠 Главное меню")
async def back_to_main_menu(message: Message):
    user_id = message.from_user.id
    search_mode[user_id] = False
    await send_welcome(message)


# === Главное меню: Расписание ===
@bot.message_handler(func=lambda m: m.text == "📅 Расписание")
async def main_schedule(message: Message):
    user_id = message.from_user.id
    search_mode[user_id] = False
    
    saved_group = await db.get_user_group(user_id)
    
    if saved_group:
        user_groups[user_id] = saved_group
        await bot.send_message(
            message.chat.id,
            f"Ваша группа: <b>{saved_group}</b>\nВыберите день:",
            reply_markup=create_schedule_keyboard(),
            parse_mode="HTML"
        )
    else:
        await bot.send_message(
            message.chat.id,
            "Выберите свой курс:",
            reply_markup=create_courses_keyboard()
        )


# === Главное меню: Поиск по преподавателю ===
@bot.message_handler(func=lambda m: m.text == "🔍 Поиск по преподавателю")
async def search_teacher_start(message: Message):
    user_id = message.from_user.id
    search_mode[user_id] = True

    await bot.send_message(
        message.chat.id,
        "🔍 Введите фамилию преподавателя (например, <b>Иванов</b>):\n\n"
        "<i>Или нажмите кнопку ниже, чтобы вернуться в главное меню</i>",
        parse_mode="HTML",
        reply_markup=create_back_to_main_keyboard()
    )


# === Главное меню: Все преподаватели на неделю ===
@bot.message_handler(func=lambda m: m.text == "👨‍🏫 Все преподаватели на неделю")
async def list_all_teachers(message: Message):
    user_id = message.from_user.id
    search_mode[user_id] = False
    
    await bot.send_message(message.chat.id, "🔄 Собираю список всех преподавателей...")

    all_schedules = await db.get_all_schedules()

    if not all_schedules:
        await bot.send_message(
            message.chat.id,
            "❌ Расписания не загружены. Обновите через /update (админ).",
            reply_markup=create_main_menu_keyboard()
        )
        return

    teachers = set()
    pattern = re.compile(r'\b([А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?\s+[А-ЯЁ]\.[А-ЯЁ]\.)')

    for group, schedule_data in all_schedules.items():
        for day_key in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']:
            day_data = schedule_data.get(day_key, {})
            for lesson in day_data.get('lessons', []):
                matches = pattern.findall(lesson)
                for match in matches:
                    teachers.add(match.strip())

    if not teachers:
        await bot.send_message(
            message.chat.id,
            "😔 Преподаватели не найдены.",
            reply_markup=create_main_menu_keyboard()
        )
        return

    teachers_list = sorted(teachers)
    response = "👨‍🏫 <b>Все преподаватели на этой неделе:</b>\n\n"
    for i, teacher in enumerate(teachers_list, 1):
        response += f"{i}. {teacher}\n"
    response += f"\nВсего: <b>{len(teachers_list)}</b> уникальных."

    await bot.send_message(
        message.chat.id,
        response,
        parse_mode="HTML",
        reply_markup=create_main_menu_keyboard()
    )


# === Обработка ввода фамилии (только в режиме поиска) ===
@bot.message_handler(func=lambda m: m.text and m.from_user.id in search_mode and search_mode[m.from_user.id])
async def handle_teacher_search_input(message: Message):
    user_id = message.from_user.id

    if message.text == "🔙 В главное меню":
        search_mode[user_id] = False
        await send_welcome(message)
        return

    if message.text.startswith("/"):
        return

    surname = message.text.strip().title()
    if len(surname) < 2:
        await bot.send_message(
            message.chat.id,
            "⚠️ Фамилия слишком короткая. Попробуйте ещё раз:",
            reply_markup=create_back_to_main_keyboard()
        )
        return

    await bot.send_message(message.chat.id, f"🔄 Ищу пары у <b>{surname}</b>...", parse_mode="HTML")

    all_schedules = await db.get_all_schedules()
    if not all_schedules:
        await bot.send_message(
            message.chat.id,
            "❌ Расписания не загружены.",
            reply_markup=create_main_menu_keyboard()
        )
        search_mode[user_id] = False
        return

    found_lessons = []
    days_russian = {
        'monday': 'Понедельник', 'tuesday': 'Вторник', 'wednesday': 'Среда',
        'thursday': 'Четверг', 'friday': 'Пятница', 'saturday': 'Суббота',
    }

    for group, schedule_data in all_schedules.items():
        for day_key, day_data in schedule_data.items():
            if day_key not in days_russian:
                continue
            date_str = day_data.get('date', '')
            full_day = f"{days_russian[day_key]} ({date_str})" if date_str else days_russian[day_key]
            for lesson in day_data.get('lessons', []):
                if re.search(rf'\b{re.escape(surname)}\b', lesson, re.IGNORECASE):
                    found_lessons.append(f"<b>{full_day}</b> | <i>{group}</i>\n{lesson}")

    response_text = (
        f"🔍 Найдено у <b>{surname}</b>:\n\n" + "\n\n".join(found_lessons)
        if found_lessons
        else f"😔 На этой неделе у <b>{surname}</b> пар не найдено."
    )

    await bot.send_message(
        message.chat.id,
        response_text,
        parse_mode="HTML",
        reply_markup=create_main_menu_keyboard()
    )
    search_mode[user_id] = False


# === Выбор курса ===
@bot.message_handler(func=lambda m: m.text in GROUPS_BY_COURSE.keys())
async def handle_course_selection(message: Message):
    search_mode[message.from_user.id] = False
    course = message.text
    await bot.send_message(
        message.chat.id,
        f"Выбран курс: <b>{course}</b>. Теперь выберите группу:",
        reply_markup=create_groups_keyboard(course),
        parse_mode="HTML"
    )


# === Назад к курсам ===
@bot.message_handler(func=lambda m: m.text == "Назад к курсам")
async def handle_back_to_courses(message: Message):
    search_mode[message.from_user.id] = False
    await bot.send_message(
        message.chat.id,
        "Выберите свой курс:",
        reply_markup=create_courses_keyboard()
    )


# === Выбор группы ===
@bot.message_handler(func=lambda m: any(m.text in groups for groups in GROUPS_BY_COURSE.values()))
async def handle_group_selection(message: Message):
    search_mode[message.from_user.id] = False
    group = message.text.strip()
    user_id = message.from_user.id
    user_groups[user_id] = group
    await db.save_user_preference(user_id, group)
    
    await bot.send_message(
        message.chat.id,
        f"✅ Выбрана группа: <b>{group}</b>\nВыберите день:",
        reply_markup=create_schedule_keyboard(),
        parse_mode="HTML"
    )


# === Расписание по дням ===
@bot.message_handler(func=lambda m: m.text in DAYS_MAPPING.keys())
async def send_schedule(message: Message):
    search_mode[message.from_user.id] = False
    day_text = message.text.strip()
    day_key = DAYS_MAPPING[day_text]
    
    user_id = message.from_user.id
    
    if user_id not in user_groups:
        await bot.send_message(message.chat.id, "Сначала выберите группу:", reply_markup=create_courses_keyboard())
        return
    
    if day_key == "change_group":
        await bot.send_message(message.chat.id, "Выберите новый курс:", reply_markup=create_courses_keyboard())
        return
    
    group = user_groups[user_id]
    schedule_data = await db.get_schedule(group)
    
    if not schedule_data:
        await bot.send_message(message.chat.id, f"❌ Расписание для <b>{group}</b> не найдено.", parse_mode="HTML")
        return
    
    await db.log_request(user_id, group, day_text)
    
    response = format_weekly_schedule(schedule_data, group) if day_key == "week" else format_daily_schedule(schedule_data, day_key, day_text, group)
    
    await bot.send_message(message.chat.id, response, parse_mode="HTML")


# === Админ-команды (твои оригинальные) ===
@bot.message_handler(commands=['stats'])
async def send_stats(message: Message):
    search_mode[message.from_user.id] = False
    stats = await db.get_statistics()
    response = "📊 <b>Статистика бота:</b>\n\n"
    response += f"👥 Всего пользователей: <b>{stats.get('total_users', 0)}</b>\n"
    response += f"📨 Всего запросов: <b>{stats.get('total_requests', 0)}</b>\n"
    popular = stats.get('popular_groups', [])
    if popular:
        response += "\n🏆 <b>Популярные группы:</b>\n"
        for g in popular:
            response += f"  • <code>{g['_id']}</code>: {g['count']} запросов\n"
    await bot.send_message(message.chat.id, response, parse_mode='HTML')

@bot.message_handler(commands=['clearcache'])
async def clear_cache(message: Message):
    search_mode[message.from_user.id] = False
    await db.cleanup_old_data(days_old=1)
    await bot.send_message(message.chat.id, "✅ Кэш успешно очищен! 🧹")

@bot.message_handler(commands=['dbinfo'])
async def db_info(message: Message):
    search_mode[message.from_user.id] = False
    info = await db.get_database_info()
    response = "🗃️ <b>Информация о базе данных:</b>\n\n"
    response += f"📁 Путь: <code>{info.get('database_path', 'data/schedule_bot.db')}</code>\n\n"
    tables = info.get('tables', {})
    if tables:
        response += "<b>Таблицы:</b>\n"
        for table, count in tables.items():
            response += f"  • <code>{table}</code>: <b>{count}</b> записей\n"
    await bot.send_message(message.chat.id, response, parse_mode='HTML')

@bot.message_handler(commands=['update'])
async def update_schedules(message: Message):
    search_mode[message.from_user.id] = False
    await bot.send_message(message.chat.id, "🔄 Начинаем обновление всех расписаний...")
    count = await preload_all_schedules()
    await bot.send_message(message.chat.id, f"✅ Обновление завершено! Загружено расписаний: <b>{count}</b>", parse_mode='HTML')

@bot.message_handler(commands=['help', 'помощь'])
async def send_help(message: Message):
    search_mode[message.from_user.id] = False
    help_text = """
🤖 <b>Команды бота</b>

📅 <b>Расписание:</b> выберите группу и день
🔍 <b>Поиск по преподавателю:</b> введите фамилию
👨‍🏫 <b>Все преподаватели:</b> список на неделю

Админ: /stats, /dbinfo, /clearcache, /update

Используйте кнопки ниже 👇
    """
    await bot.send_message(message.chat.id, help_text, parse_mode='HTML')


# === Ловец остальных сообщений (дружелюбный) ===
@bot.message_handler(func=lambda m: True)
async def handle_other(message: Message):
    user_id = message.from_user.id
    search_mode[user_id] = False
    
    if user_id in user_groups:
        group = user_groups[user_id]
        await bot.send_message(
            message.chat.id,
            f"🤔 Не понял, что вы имели в виду.\n\n"
            f"Вот расписание для группы <b>{group}</b>. Выберите день:",
            reply_markup=create_schedule_keyboard(),
            parse_mode="HTML"
        )
    else:
        await bot.send_message(
            message.chat.id,
            "🤔 Не понял команду.\n\n"
            "Давайте начнём сначала:",
            reply_markup=create_main_menu_keyboard()
        )
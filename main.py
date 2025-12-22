import asyncio
import os
from telebot.async_telebot import AsyncTeleBot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
import urllib3
import re
from datetime import datetime

# Импортируем SQLite базу данных и парсер
from database import db
from get_rasp import get_info

load_dotenv()
urllib3.disable_warnings()

TOKEN = os.getenv('BOT_TOKEN')

if not TOKEN:
    raise ValueError("BOT_TOKEN не установлен! Проверьте файл .env")

BASE_URL = 'https://oksei.ru/studentu/raspisanie_uchebnykh_zanyatij'

GROUPS_BY_COURSE = {
    "1 курс": [
        "1а1", "1бд1", "1бд3", "1бп1", "1бу1", "1бу3", "1вб1", "1вб2", "1вб3(б)",
        "1д1", "1д3", "1ис1", "1ис2", "1ис3", "1м1", "1пк1", "1пк2", "1р1", "1р3",
        "1са1", "1са2", "1са3"
    ],
    "2 курс": [
        "2а1", "2бд1", "2бд3", "2бп3", "2бу1", "2бу3", "2вб1", "2вб2", "2вб3",
        "2д1", "2д3", "2ис1", "2ис3", "2м1", "2пк1", "2пк2", "2р1", "2р3",
        "2са1", "2са3"
    ],
    "3 курс": [
        "3а1", "3бд1", "3бд3", "3бу1", "3бу3", "3вб1", "3вб2", "3вб3", "3д1",
        "3д3", "3ис1", "3ис3", "3м1", "3пк1", "3пк2", "3р1", "3р3", "3са1", "3са3"
    ],
    "4 курс": [
        "4бу1", "4вб1", "4вб2", "4вб3", "4д1", "4ис1", "4ис3", "4м1", "4пк1",
        "4пк2", "4р1", "4р3"
    ]
}

DAYS_MAPPING = {
    "Понедельник": "monday",
    "Вторник": "tuesday", 
    "Среда": "wednesday",
    "Четверг": "thursday",
    "Пятница": "friday",
    "Суббота": "saturday",
    "Вся неделя": "week",
    "Сменить группу": "change_group"
}

# Хранилище выбранных групп пользователей (временное, пока сессия активна)
user_groups = {}

# Инициализация асинхронного бота
bot = AsyncTeleBot(TOKEN)

async def preload_all_schedules():
    """
    Предварительная загрузка расписаний всех групп в базу данных.
    Выполняется при запуске бота.
    """
    print("🚀 Начинаем предварительную загрузку расписаний...")
    
    all_groups = []
    for groups_list in GROUPS_BY_COURSE.values():
        all_groups.extend(groups_list)
    
    total_groups = len(all_groups)
    print(f"📋 Всего групп для загрузки: {total_groups}")
    
    loaded_count = 0
    failed_count = 0
    
    # Определяем начало текущей недели
    week_start = datetime.now().strftime("%Y-%m-%d")
    
    for i, group_name in enumerate(all_groups, 1):
        try:
            # Проверяем, есть ли уже расписание для этой группы
            existing_schedule = await db.get_schedule(group_name, week_start)
            
            if existing_schedule:
                print(f"✅ [{i}/{total_groups}] Расписание для {group_name} уже в БД")
                loaded_count += 1
                continue
            
            # Если нет - парсим
            print(f"🌐 [{i}/{total_groups}] Парсим расписание для {group_name}...")
            url = f"{BASE_URL}?group={group_name}"
            
            try:
                schedule_data = await get_info(url)
                
                if schedule_data and any(day in schedule_data for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']):
                    # Сохраняем в базу данных
                    await db.save_schedule(group_name, schedule_data, week_start)
                    loaded_count += 1
                    print(f"✅ [{i}/{total_groups}] Расписание для {group_name} успешно загружено")
                else:
                    print(f"⚠️ [{i}/{total_groups}] Для группы {group_name} не найдено расписание")
                    failed_count += 1
                    
            except Exception as e:
                print(f"❌ [{i}/{total_groups}] Ошибка при парсинге {group_name}: {e}")
                failed_count += 1
            
            # Небольшая задержка между запросами, чтобы не нагружать сервер
            if i % 5 == 0:
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"❌ [{i}/{total_groups}] Критическая ошибка для {group_name}: {e}")
            failed_count += 1
    
    print(f"\n🎯 Итог предварительной загрузки:")
    print(f"   ✅ Успешно загружено: {loaded_count} групп")
    print(f"   ❌ Не удалось загрузить: {failed_count} групп")
    print(f"   📊 Всего обработано: {total_groups} групп")
    
    return loaded_count

async def update_old_schedules():
    """
    Обновление устаревших расписаний в базе данных.
    """
    print("\n🔄 Проверка устаревших расписаний...")
    
    # Проверяем, какие расписания старше 1 дня
    try:
        await db.cleanup_old_data(days_old=1)
        print("✅ Устаревшие расписания обновлены")
    except Exception as e:
        print(f"⚠️ Ошибка при обновлении расписаний: {e}")

def create_courses_keyboard():
    """Клавиатура для выбора курса"""
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    for course in GROUPS_BY_COURSE.keys():
        item_button = KeyboardButton(course)
        markup.add(item_button)
    
    return markup

def create_groups_keyboard(course):
    """Клавиатура для выбора группы по курсу"""
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    groups = GROUPS_BY_COURSE.get(course, [])
    
    for i in range(0, len(groups), 2):
        row = []
        if i < len(groups):
            row.append(KeyboardButton(groups[i]))
        if i + 1 < len(groups):
            row.append(KeyboardButton(groups[i + 1]))
        if row:
            markup.add(*row)
    
    markup.add(KeyboardButton("Назад к курсам"))
    
    return markup

def create_schedule_keyboard():
    """Клавиатура для выбора дня недели"""
    markup = ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    
    markup.add(
        KeyboardButton("Понедельник"), 
        KeyboardButton("Вторник"), 
        KeyboardButton("Среда")
    )
    markup.add(
        KeyboardButton("Четверг"), 
        KeyboardButton("Пятница"), 
        KeyboardButton("Суббота")
    )
    markup.add(
        KeyboardButton("Вся неделя"),
        KeyboardButton("Сменить группу")
    )
    
    return markup

async def get_schedule_from_db(group_name, day="week"):
    """
    Получает расписание ТОЛЬКО из базы данных.
    Если нет в БД - сообщает пользователю.
    
    Args:
        group_name (str): Название группы
        day (str): День недели
        
    Returns:
        Tuple[Optional[Dict], str]: (Данные расписания, Сообщение об ошибке/предупреждении)
    """
    try:
        # Получаем из БД
        schedule_data = await db.get_schedule(group_name)
        
        if schedule_data:
            print(f"📦 Расписание для {group_name} получено из SQLite")
            return schedule_data, ""
        else:
            print(f"⚠️ Расписание для {group_name} не найдено в БД")
            return None, f"Расписание для группы {group_name} не найдено в базе данных.\nПопробуйте позже или обратитесь к администратору."
            
    except Exception as e:
        print(f"❌ Ошибка при получении расписания из БД: {e}")
        return None, f"Ошибка при получении расписания из базы данных."

@bot.message_handler(commands=['start'])
async def send_welcome(message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    # Проверяем, есть ли сохраненная группа у пользователя в БД
    saved_group = await db.get_user_group(user_id)
    if saved_group:
        user_groups[user_id] = saved_group
        markup = create_schedule_keyboard()
        username = message.from_user.username or message.from_user.first_name
        await bot.send_message(
            message.chat.id,
            f"С возвращением, {username}! Ваша группа: {saved_group}\nВыберите день:",
            reply_markup=markup
        )
        return
    
    # Если нет сохраненной группы, показываем выбор курса
    markup = create_courses_keyboard()
    username = message.from_user.username or message.from_user.first_name
    await bot.send_message(
        message.chat.id,
        f"Привет, {username}! Выбери свой курс:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text in GROUPS_BY_COURSE.keys())
async def handle_course_selection(message):
    """Обработчик выбора курса"""
    selected_course = message.text
    
    markup = create_groups_keyboard(selected_course)
    await bot.send_message(
        message.chat.id,
        f"Выбран курс: {selected_course}. Теперь выбери группу:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "Назад к курсам")
async def handle_back_to_courses(message):
    """Обработчик кнопки 'Назад к курсам'"""
    markup = create_courses_keyboard()
    await bot.send_message(
        message.chat.id,
        "Выбери свой курс:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: any(
    message.text in groups for groups in GROUPS_BY_COURSE.values()
))
async def handle_group_selection(message):
    """Обработчик выбора группы"""
    user_id = message.from_user.id
    selected_group = message.text
    
    user_groups[user_id] = selected_group
    
    # Сохраняем предпочтение пользователя в SQLite
    await db.save_user_preference(user_id, selected_group)
    
    markup = create_schedule_keyboard()
    await bot.send_message(
        message.chat.id,
        f"Выбрана группа: {selected_group}. Теперь выбери день:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text in DAYS_MAPPING.keys())
async def send_schedule(message):
    """Обработчик запроса расписания"""
    user_id = message.from_user.id
    selected_day = message.text
    day_key = DAYS_MAPPING[selected_day]
    
    if user_id not in user_groups:
        markup = create_courses_keyboard()
        await bot.send_message(
            message.chat.id,
            "Сначала выбери свою группу:",
            reply_markup=markup
        )
        return
    
    if day_key == "change_group":
        markup = create_courses_keyboard()
        await bot.send_message(
            message.chat.id,
            "Выбери новый курс:",
            reply_markup=markup
        )
        return
    
    group_name = user_groups[user_id]
    
    try:
        # Получаем расписание ТОЛЬКО из БД
        schedule_data, error_message = await get_schedule_from_db(group_name)
        
        if error_message:
            await bot.send_message(message.chat.id, error_message)
            return
        
        # Логируем запрос
        await db.log_request(user_id, group_name, selected_day)
        
        if day_key == "week":
            response = format_weekly_schedule(schedule_data, group_name)
        else:
            response = format_daily_schedule(schedule_data, day_key, selected_day, group_name)
        
        await bot.send_message(message.chat.id, response)
        
    except Exception as e:
        print(f"Ошибка при получении расписания: {e}")
        await bot.send_message(
            message.chat.id,
            f"Ошибка при получении расписания. Попробуйте позже."
        )

def format_daily_schedule(schedule_data, day_key, day_name, group_name):
    """Форматирование расписания на один день"""
    if not schedule_data or day_key not in schedule_data:
        return f"Группа: {group_name}\n{day_name}\n\nДанные не найдены"
    
    day_data = schedule_data.get(day_key, {})
    lessons = day_data.get('lessons', [])
    date = day_data.get('date', '')
    
    if not lessons:
        if date:
            return f"Группа: {group_name}\n{date}\n{day_name}\n\nЗанятий нет 🎉"
        else:
            return f"Группа: {group_name}\n{day_name}\n\nЗанятий нет 🎉"
    
    response = f"Группа: {group_name}\n"
    if date:
        response += f"{date}\n"
    response += f"{day_name}:\n\n"
    
    for i, lesson in enumerate(lessons, 1):
        response += f"{i}. {lesson}\n"
    
    return response

def format_weekly_schedule(schedule_data, group_name):
    """Форматирование расписания на всю неделю"""
    if not schedule_data:
        return f"РАСПИСАНИЕ НА НЕДЕЛЮ\nГруппа: {group_name}\n\nДанные не найдены"
    
    day_names = {
        'monday': 'ПОНЕДЕЛЬНИК',
        'tuesday': 'ВТОРНИК', 
        'wednesday': 'СРЕДА',
        'thursday': 'ЧЕТВЕРГ',
        'friday': 'ПЯТНИЦА',
        'saturday': 'СУББОТА'
    }
    
    date_range = schedule_data.get('date_range', '')
    current_day_date = schedule_data.get('current_day', '')
    
    response = f"РАСПИСАНИЕ НА НЕДЕЛЮ\nГруппа: {group_name}\n"
    
    if date_range:
        response += f"Период: {date_range}\n"
    if current_day_date:
        response += f"Сегодня: {current_day_date}\n"
    
    response += "\n" + "="*30 + "\n\n"
    
    for day_key, day_name in day_names.items():
        day_data = schedule_data.get(day_key, {})
        lessons = day_data.get('lessons', [])
        date = day_data.get('date', '')
        
        response += f"▫️ {day_name}\n"
        if date:
            response += f"📅 {date}\n"
        
        if lessons:
            for i, lesson in enumerate(lessons, 1):
                response += f"  {i}. {lesson}\n"
        else:
            response += "  🎉 Занятий нет\n"
        
        response += "\n"
    
    # Обрезаем если слишком длинное сообщение
    if len(response) > 4000:
        response = response[:4000] + "\n\n... (сообщение слишком длинное)"
    
    return response

# Новые команды для административных функций
@bot.message_handler(commands=['stats'])
async def send_stats(message):
    """Показать статистику использования бота"""
    try:
        stats = await db.get_statistics()
        
        response = "📊 **Статистика бота:**\n\n"
        response += f"👥 Всего пользователей: {stats.get('total_users', 0)}\n"
        response += f"📨 Всего запросов: {stats.get('total_requests', 0)}\n"
        
        popular_groups = stats.get('popular_groups', [])
        if popular_groups:
            response += "\n🏆 **Популярные группы:**\n"
            for group in popular_groups:
                response += f"  • {group['_id']}: {group['count']} запросов\n"
        
        await bot.send_message(message.chat.id, response, parse_mode='Markdown')
        
    except Exception as e:
        print(f"Ошибка получения статистики: {e}")
        await bot.send_message(message.chat.id, "Не удалось получить статистику.")

@bot.message_handler(commands=['clearcache'])
async def clear_cache(message):
    """Очистка кэша"""
    try:
        await db.cleanup_old_data(days_old=1)
        await bot.send_message(message.chat.id, "✅ Кэш успешно очищен!")
    except Exception as e:
        await bot.send_message(message.chat.id, f"❌ Ошибка очистки кэша: {e}")

@bot.message_handler(commands=['dbinfo'])
async def show_db_info(message):
    """Показать информацию о базе данных"""
    try:
        info = await db.get_database_info()
        
        response = "🗃️ **Информация о базе данных:**\n\n"
        response += f"📁 Файл БД: `{info.get('database_path', 'schedule_bot.db')}`\n"
        
        tables = info.get('tables', {})
        if tables:
            response += "\n📊 **Таблицы:**\n"
            for table, count in tables.items():
                response += f"  • {table}: {count} записей\n"
        
        await bot.send_message(message.chat.id, response, parse_mode='Markdown')
        
    except Exception as e:
        print(f"Ошибка получения информации о БД: {e}")
        await bot.send_message(message.chat.id, "Не удалось получить информацию о БД.")

@bot.message_handler(commands=['update'])
async def update_schedules(message):
    """Обновить все расписания (только для админов)"""
    # Можно добавить проверку на админа
    user_id = message.from_user.id
    
    await bot.send_message(message.chat.id, "🔄 Начинаем обновление расписаний...")
    
    try:
        loaded_count = await preload_all_schedules()
        await bot.send_message(
            message.chat.id, 
            f"✅ Обновление завершено!\nЗагружено расписаний: {loaded_count}"
        )
    except Exception as e:
        await bot.send_message(
            message.chat.id, 
            f"❌ Ошибка при обновлении: {e}"
        )

@bot.message_handler(commands=['help', 'помощь'])
async def send_help(message):
    """Показать справку"""
    help_text = """
🤖 **Команды бота:**

/start - Начать работу с ботом
/help - Показать эту справку
/stats - Показать статистику использования
/dbinfo - Информация о базе данных
/clearcache - Очистить кэш (админ)

📅 **Как пользоваться:**
1. Выберите свой курс
2. Выберите свою группу
3. Выберите день недели или "Вся неделя"
4. Получите расписание!

⚡ **Особенности:**
- Расписание загружается заранее в базу данных
- Быстрый доступ к данным
- Автоматическое обновление устаревших расписаний
- Сохранение ваших предпочтений
    """
    await bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
async def handle_other_messages(message):
    """Обработчик всех остальных сообщений"""
    user_id = message.from_user.id
    
    if user_id in user_groups:
        markup = create_schedule_keyboard()
        await bot.send_message(
            message.chat.id,
            "Используй кнопки для выбора дня:",
            reply_markup=markup
        )
    else:
        markup = create_courses_keyboard()
        await bot.send_message(
            message.chat.id,
            "Сначала выбери свой курс:",
            reply_markup=markup
        )

async def main():
    """Основная асинхронная функция запуска бота"""
    print('=' * 50)
    print('🚀 ЗАПУСК БОТА РАСПИСАНИЯ ОКЭИ')
    print('=' * 50)
    
    # Подключаемся к базе данных
    await db.connect()
    
    # Предварительная загрузка расписаний
    await preload_all_schedules()
    
    # Обновление устаревших расписаний
    await update_old_schedules()
    
    print('\n🤖 Бот готов к работе!')
    print('Для остановки нажмите Ctrl+C')
    print('=' * 50)
    
    try:
        await bot.polling(none_stop=True, interval=0)
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")
    finally:
        # Закрываем подключение к базе данных при выходе
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
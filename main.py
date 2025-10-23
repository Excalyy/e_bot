from telebot import TeleBot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from get_rasp import get_info
from config import TOKEN

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

user_groups = {}

bot = TeleBot(TOKEN)

def create_courses_keyboard():
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    for course in GROUPS_BY_COURSE.keys():
        item_button = KeyboardButton(course)
        markup.add(item_button)
    
    return markup

def create_groups_keyboard(course):
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

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    markup = create_courses_keyboard()
    username = message.from_user.username or message.from_user.first_name
    bot.send_message(
        message.chat.id,
        f"Привет, {username}! Выбери свой курс:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text in GROUPS_BY_COURSE.keys())
def handle_course_selection(message):
    selected_course = message.text
    
    markup = create_groups_keyboard(selected_course)
    bot.send_message(
        message.chat.id,
        f"Выбран курс: {selected_course}. Теперь выбери группу:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "Назад к курсам")
def handle_back_to_courses(message):
    markup = create_courses_keyboard()
    bot.send_message(
        message.chat.id,
        "Выбери свой курс:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: any(
    message.text in groups for groups in GROUPS_BY_COURSE.values()
))
def handle_group_selection(message):
    user_id = message.from_user.id
    selected_group = message.text
    
    user_groups[user_id] = selected_group
    
    markup = create_schedule_keyboard()
    bot.send_message(
        message.chat.id,
        f"Выбрана группа: {selected_group}. Теперь выбери день:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text in DAYS_MAPPING.keys())
def send_schedule(message):
    user_id = message.from_user.id
    selected_day = message.text
    day_key = DAYS_MAPPING[selected_day]
    
    if user_id not in user_groups:
        markup = create_courses_keyboard()
        bot.send_message(
            message.chat.id,
            "Сначала выбери свою группу:",
            reply_markup=markup
        )
        return
    
    if day_key == "change_group":
        markup = create_courses_keyboard()
        bot.send_message(
            message.chat.id,
            "Выбери новый курс:",
            reply_markup=markup
        )
        return
    
    group_name = user_groups[user_id]
    
    url = f"{BASE_URL}?group={group_name}"
    
    try:
        schedule_data = get_info(url)
        
        if day_key == "week":
            response = format_weekly_schedule(schedule_data, group_name)
        else:
            response = format_daily_schedule(schedule_data, day_key, selected_day, group_name)
        
        bot.send_message(message.chat.id, response)
        
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"Ошибка при получении расписания: {e}"
        )

def format_daily_schedule(schedule_data, day_key, day_name, group_name):
    lessons = schedule_data.get(day_key, [])
    
    if not lessons:
        return "Занятий нет"
    
    response = f"Группа: {group_name}\n{day_name}:\n\n"
    for lesson in lessons:
        response += f"{lesson}\n"
    
    return response

def format_weekly_schedule(schedule_data, group_name):
    day_names = {
        'monday': 'ПОНЕДЕЛЬНИК',
        'tuesday': 'ВТОРНИК',
        'wednesday': 'СРЕДА',
        'thursday': 'ЧЕТВЕРГ', 
        'friday': 'ПЯТНИЦА',
        'saturday': 'СУББОТА'
    }
    
    response = f"РАСПИСАНИЕ НА НЕДЕЛЮ\nГруппа: {group_name}\n\n"
    
    for day_key, day_name in day_names.items():
        lessons = schedule_data.get(day_key, [])
        
        response += f"{day_name}:\n"
        if lessons:
            for lesson in lessons:
                response += f"{lesson}\n"
        else:
            response += "Выходной\n"
        response += "\n"
    
    if len(response) > 4000:
        parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
        return parts[0]  
    
    return response

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    user_id = message.from_user.id
    
    if user_id in user_groups:
        markup = create_schedule_keyboard()
        bot.send_message(
            message.chat.id,
            "Используй кнопки для выбора дня:",
            reply_markup=markup
        )
    else:
        markup = create_courses_keyboard()
        bot.send_message(
            message.chat.id,
            "Сначала выбери свой курс:",
            reply_markup=markup
        )

if __name__ == "__main__":
    print('Бот запущен...')
    bot.infinity_polling()
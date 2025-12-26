from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from .constants import GROUPS_BY_COURSE


def create_courses_keyboard():
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    for course in GROUPS_BY_COURSE.keys():
        markup.add(KeyboardButton(course))
    # Добавляем кнопку в отдельной строке внизу
    markup.row(KeyboardButton("🏠 Главное меню"))
    return markup


def create_groups_keyboard(course: str):
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
    markup.row(KeyboardButton("Назад к курсам"))
    markup.row(KeyboardButton("🏠 Главное меню"))  # отдельная кнопка внизу
    return markup


def create_schedule_keyboard():
    markup = ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    markup.add("Понедельник", "Вторник", "Среда")
    markup.add("Четверг", "Пятница", "Суббота")
    markup.add("Вся неделя", "Сменить группу")
    markup.row(KeyboardButton("🏠 Главное меню"))  # отдельная строка внизу
    return markup


def create_main_menu_keyboard():
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        KeyboardButton("📅 Расписание"),
        KeyboardButton("🔍 Поиск по преподавателю")
    )
    markup.add(KeyboardButton("👨‍🏫 Все преподаватели на неделю"))
    return markup


def create_back_to_main_keyboard():
    markup = ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(KeyboardButton("🔙 В главное меню"))
    return markup
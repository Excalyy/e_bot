from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from .constants import GROUPS_BY_COURSE


def create_courses_keyboard():
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    for course in GROUPS_BY_COURSE.keys():
        markup.add(KeyboardButton(course))
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
    markup.add(KeyboardButton("Назад к курсам"))
    return markup

def create_schedule_keyboard():
    markup = ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    markup.add("Понедельник", "Вторник", "Среда")
    markup.add("Четверг", "Пятница", "Суббота")
    markup.add("Вся неделя", "Сменить группу")
    return markup
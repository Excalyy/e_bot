def format_daily_schedule(schedule_data, day_key, day_name, group_name):
    """Форматирование расписания на один день — без лишней нумерации"""
    if not schedule_data or day_key not in schedule_data:
        return f"Группа: {group_name}\n{day_name}\n\nДанные не найдены"
    
    day_data = schedule_data.get(day_key, {})
    lessons = day_data.get('lessons', [])
    date = day_data.get('date', '')
    
    if not lessons:
        return f"Группа: {group_name}\n{date}\n{day_name}\n\nЗанятий нет 🎉"
    
    response = f"Группа: {group_name}\n"
    if date:
        response += f"{date}\n"
    response += f"{day_name}:\n\n"
    
    # Просто выводим уроки как есть — там уже есть номер пары
    for lesson in lessons:
        response += f"{lesson}\n"
    
    return response

def format_weekly_schedule(schedule_data, group_name):
    """Форматирование расписания на всю неделю — без лишней нумерации"""
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
            response += f"{date}\n"
        
        if lessons:
            # Просто выводим каждый урок как есть — номер пары уже внутри строки
            for lesson in lessons:
                response += f"  {lesson}\n"
        else:
            response += "  🎉 Занятий нет\n"
        
        response += "\n"
    
    # Обрезаем, если слишком длинное
    if len(response) > 4000:
        response = response[:4000] + "\n\n... (сообщение слишком длинное)"
    
    return response
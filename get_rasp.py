import asyncio
import aiohttp
from bs4 import BeautifulSoup as BS
from fake_useragent import UserAgent
import requests
import re
from datetime import datetime
import ssl

user_agent = UserAgent().random
headers = { 
     'user_agent': user_agent
 }
headers = {'user-agent': user_agent}

def get_info(url):
    response = requests.get(url, verify=False, headers=headers)
    html = BS(response.content, 'html.parser')
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

async def fetch_html(session, url):
    """Асинхронное получение HTML контента"""
    try:
        async with session.get(url, headers=headers, ssl=ssl_context) as response:
            response.raise_for_status()
            return await response.text()
    except Exception as e:
        print(f"Ошибка при получении {url}: {e}")
        return None

async def get_info(url):
    """Асинхронная версия функции get_info"""
    async with aiohttp.ClientSession() as session:
        html_content = await fetch_html(session, url)
        
        if not html_content:
            return {}
        
        html = BS(html_content, 'html.parser')
        
        schedule_dict = {}
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
        
        title_tag = html.find('p', align="center")
        date_range = ""
        if title_tag:
            date_text = title_tag.get_text(strip=True)
            date_match = re.search(r'на\s+(\d{2}\.\d{2}\.\d{4}-\d{2}\.\d{2}\.\d{4})', date_text)
            if date_match:
                date_range = date_match.group(1)
        
        week_dates = get_week_dates(date_range)
        
        for day in days:
            day_cell = html.find('td', id=day)
            if day_cell:
                lessons = day_cell.find_all('li')
                day_lessons = []
                
                for lesson in lessons:
                    text = lesson.get_text(strip=True)
                    if text:
                        day_lessons.append(text)
                
                schedule_dict[day] = {
                    'lessons': day_lessons,
                    'date': week_dates.get(day, '')
                }
        
        schedule_dict['date_range'] = date_range
        schedule_dict['current_day'] = get_current_day_date(date_range)
        
        return schedule_dict

async def get_info_multiple_urls(urls):
    """Получение информации с нескольких URL асинхронно"""
    tasks = []
    async with aiohttp.ClientSession() as session:
        for url in urls:
            task = asyncio.create_task(fetch_and_process(session, url))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

async def fetch_and_process(session, url):
    """Получение и обработка HTML для одного URL"""
    html_content = await fetch_html(session, url)
    
    if not html_content:
        return {}
    
    return process_html_content(html_content)

def process_html_content(html_content):
    """Обработка HTML контента (синхронная часть)"""
    html = BS(html_content, 'html.parser')

    schedule_dict = {}
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']

    title_tag = html.find('p', align="center")
    date_range = ""
    if title_tag:
        date_text = title_tag.get_text(strip=True)
        date_match = re.search(r'на\s+(\d{2}\.\d{2}\.\d{4}-\d{2}\.\d{2}\.\d{4})', date_text)
        if date_match:
            date_range = date_match.group(1)

    week_dates = get_week_dates(date_range)

    for day in days:
        day_cell = html.find('td', id=day)
        if day_cell:
            lessons = day_cell.find_all('li')
            day_lessons = []

            for lesson in lessons:
                text = lesson.get_text(strip=True)
                if text:
                    day_lessons.append(text)

            schedule_dict[day] = {
                'lessons': day_lessons,
                'date': week_dates.get(day, '')
            }

    schedule_dict['date_range'] = date_range
    schedule_dict['current_day'] = get_current_day_date(date_range)

    return schedule_dict

def get_current_day_date(date_range):
    if not date_range:
        return ""

    try:
        start_date_str, end_date_str = date_range.split('-')

        start_date = datetime.strptime(start_date_str, '%d.%m.%Y')
        end_date = datetime.strptime(end_date_str, '%d.%m.%Y')

        current_weekday = datetime.now().weekday()

        if current_weekday == 6:
            return ""

        days_diff = current_weekday
        current_day_date = start_date

        for i in range(days_diff):
            current_day_date = get_next_weekday(current_day_date)

        if start_date <= current_day_date <= end_date:
            return current_day_date.strftime('%d.%m.%Y')
        else:
            return ""

    except (ValueError, AttributeError):
        return ""

def get_next_weekday(date):
    next_day = date
    while True:
        next_day = next_day.replace(day=next_day.day + 1)
        if next_day.weekday() != 6:
            return next_day

def get_week_dates(date_range):
    if not date_range:
        return {}

    try:
        start_date_str, end_date_str = date_range.split('-')
        start_date = datetime.strptime(start_date_str, '%d.%m.%Y')

        week_dates = {}
        days_mapping = {
            'monday': 0,
            'tuesday': 1, 
            'wednesday': 2,
            'thursday': 3,
            'friday': 4,
            'saturday': 5
        }

        current_date = start_date
        for day_name, day_index in days_mapping.items():
            while current_date.weekday() != day_index:
                current_date = current_date.replace(day=current_date.day + 1)

            week_dates[day_name] = format_date_russian(current_date)
            current_date = current_date.replace(day=current_date.day + 1)

            if current_date.weekday() == 6:
                current_date = current_date.replace(day=current_date.day + 1)

        return week_dates

    except (ValueError, AttributeError):
        return {}

def format_date_russian(date):
    months = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }

    day = date.day
    month = months[date.month]
    year = date.year

    return f"{day} {month} {year}"
    return f"{day} {month} {year}"

async def main():
    url = "https://example.com/schedule"
    
    schedule = await get_info(url)
    print(schedule)
    
    urls = [
        "https://example.com/schedule1",
        "https://example.com/schedule2",
        "https://example.com/schedule3"
    ]
    
    schedules = await get_info_multiple_urls(urls)
    for i, schedule in enumerate(schedules):
        print(f"\nSchedule {i+1}:")
        print(schedule)

if __name__ == "__main__":
    asyncio.run(main())
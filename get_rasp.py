from bs4 import BeautifulSoup as BS
from fake_useragent import UserAgent
import requests

user_agent = UserAgent().random
headers = { 
     'user_agent': user_agent
 }

def get_info(url):
    response = requests.get(url, verify=False, headers=headers)
    html = BS(response.content, 'html.parser')
    
    schedule_dict = {}
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
    for day in days:
        day_cell = html.find('td', id=day)
        if day_cell:
            lessons = day_cell.find_all('li')
            day_lessons = []
            
            for lesson in lessons:
                text = lesson.get_text(strip=True)
                if text:
                    day_lessons.append(text)
            
            schedule_dict[day] = day_lessons
    
    return schedule_dict




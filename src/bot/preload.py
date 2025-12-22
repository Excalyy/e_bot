from datetime import datetime
import asyncio

from src.config.settings import BASE_URL
from src.database.db import db
from src.parser.parser import get_info
from src.bot.constants import GROUPS_BY_COURSE
from src.utils.logger import log


async def preload_all_schedules() -> int:
    log.info("🚀 Начинаем предзагрузку расписаний всех групп...")
    all_groups = [g for groups in GROUPS_BY_COURSE.values() for g in groups]
    week_start = datetime.now().strftime("%Y-%m-%d")
    loaded = 0
    
    for i, group in enumerate(all_groups, 1):
        existing = await db.get_schedule(group, week_start)
        if existing:
            print(f"[{i}/{len(all_groups)}] {group} — уже в БД")
            loaded += 1
            continue
        
        url = f"{BASE_URL}?group={group}"
        try:
            data = await get_info(url)
            if data and any(day in data for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']):
                await db.save_schedule(group, data, week_start)
                loaded += 1
                print(f"[{i}/{len(all_groups)}] {group} — загружено")
        except Exception as e:
            print(f"Ошибка парсинга {group}: {e}")
        
        if i % 5 == 0:
            await asyncio.sleep(1)
    
    log.info(f"Готово! Загружено: {loaded}/{len(all_groups)} групп")
    return loaded
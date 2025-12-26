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
        # Проверяем, есть ли уже на эту неделю
        existing = await db.get_schedule(group, week_start)
        if existing:
            log.info(f"[{i}/{len(all_groups)}] {group} — уже в БД (пропуск)")
            loaded += 1
            continue

        url = f"{BASE_URL}?group={group}"
        try:
            data = await get_info(url)

            if not data:
                log.warning(f"[{i}/{len(all_groups)}] {group} — данные от парсера пустые (None)")
                # Всё равно сохраняем пустое расписание
                await db.save_schedule(group, {}, week_start)
                loaded += 1
                continue

            # Проверяем, есть ли уроки хотя бы в одном дне
            days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
            has_lessons = False
            empty_days = []
            filled_days = []

            for day in days:
                day_data = data.get(day, {})
                lessons = day_data.get('lessons', [])
                if lessons and any(lesson.strip() for lesson in lessons):
                    has_lessons = True
                    filled_days.append(day)
                else:
                    empty_days.append(day)

            # Сохраняем ВСЕГДА (даже пустое)
            await db.save_schedule(group, data, week_start)
            loaded += 1

            if has_lessons:
                log.info(f"[{i}/{len(all_groups)}] {group} — загружено с уроками ({len(filled_days)} дней: {', '.join(filled_days)})")
            else:
                log.warning(f"[{i}/{len(all_groups)}] {group} — расписание полностью пустое (все дни без уроков)")

        except Exception as e:
            log.error(f"[{i}/{len(all_groups)}] Ошибка при обработке {group}: {e}")
            # При ошибке тоже сохраняем пустое, чтобы группа была в БД
            await db.save_schedule(group, {}, week_start)
            loaded += 1

        # Задержка, чтобы не нагружать сайт
        if i % 5 == 0:
            await asyncio.sleep(1)

    log.info(f"✅ Предзагрузка завершена! Обработано и сохранено: {loaded}/{len(all_groups)} групп")
    return loaded
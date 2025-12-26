import flet as ft
from src.database.db import db
from src.bot.preload import preload_all_schedules
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv
import os
import re

from src.bot.constants import GROUPS_BY_COURSE

load_dotenv()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise ValueError("ADMIN_PASSWORD не установлен в .env файле!")

GROUP_FORMAT_PATTERN = re.compile(r"^[1-4][а-яё]{1,3}\d{1,2}$", re.IGNORECASE)

async def main(page: ft.Page):
    page.title = "Админ-панель расписания"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 1200
    page.window.height = 950
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    password_field = ft.TextField(label="Введите пароль", password=True, width=400)
    error_text = ft.Text(color=ft.Colors.RED)
    status_text = ft.Text(color=ft.Colors.GREEN)

    async def login(e):
        if password_field.value == ADMIN_PASSWORD:
            error_text.value = ""
            page.controls.clear()
            page.add(await admin_dashboard())
        else:
            error_text.value = "❌ Неправильный пароль"
        page.update()

    async def logout(e):
        page.controls.clear()
        password_field.value = ""
        page.add(
            ft.Column([
                ft.Text("Админ-панель расписания", size=32, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                password_field,
                ft.FilledButton("Войти", on_click=login, width=400),
                error_text
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20)
        )
        page.update()

    page.add(
        ft.Column([
            ft.Text("Админ-панель расписания", size=32, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            password_field,
            ft.FilledButton("Войти", on_click=login, width=400),
            error_text
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20)
    )

    async def admin_dashboard():
        await db.connect()

        stats = await db.get_statistics()
        info = await db.get_database_info()

        all_schedules = await db.get_all_schedules()
        available_groups = sorted(all_schedules.keys())

        # Блок "О проекте"
        about_project_block = ft.Container(
            content=ft.Column([
                ft.Text("О курсовом проекте", size=26, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_400),
                ft.Divider(height=10, color=ft.Colors.GREY_600),
                ft.Text("Тема нашего проекта:", weight=ft.FontWeight.BOLD, size=16),
                ft.Text("Разработка тг бота для получения расписания занятий (парсинга) студентов ОКЭИ с сайта", size=15),
                ft.Text("Исполнитель:", weight=ft.FontWeight.BOLD, size=16),
                ft.Text("Студент группы 4пк2", size=15),
                ft.Text("Давиденко Дмитрий Сергеевич", size=15, weight=ft.FontWeight.BOLD),
                ft.Text("Год выполнения: 2025", size=15),
                ft.Text("Что делает приложение:", weight=ft.FontWeight.BOLD, size=16),
                ft.Text("Автоматически парсит расписание с сайта oksei.ru", size=15),
                ft.Text("Позволяет пользователям выбирать группу и просматривать расписание на день или неделю", size=15),
                ft.Text("Поддерживает поиск занятий по фамилии преподавателя", size=15),
                ft.Text("Сохраняет выбранную группу для каждого пользователя", size=15),
                ft.Text("Имеет защищённую админ-панель для управления данными, статистикой и ручного добавления расписания", size=15),

                ft.Divider(height=15, color=ft.Colors.GREY_700),

                ft.Text("Тех стек:", weight=ft.FontWeight.BOLD, size=16),
                ft.Text("Python 3.13+", size=15),
                ft.Text("pyTelegramBotAPI - апи тг бота", size=15),
                ft.Text("aiosqlite - асинхронная база данных SQLite", size=15),
                ft.Text("Flet - графическая админ-панель ", size=15),
                ft.Text("BeautifulSoup4 + aiohttp/requests - парсинг сайта", size=15),
                ft.Text("python-dotenv - хранение секретов", size=15),
                ft.Text("re, json, asyncio - обработка данных", size=15),

        ft.Divider(height=15, color=ft.Colors.GREY_700),
            ], spacing=8),
            padding=20,
            bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.BLUE_GREY_900),
            border_radius=12,
            margin=ft.Margin.only(bottom=20)
        )

        # Добавление пользователя
        user_id_field = ft.TextField(label="Telegram ID пользователя", width=400, hint_text="Например: 123456789")
        course_dropdown = ft.Dropdown(
            label="Выбрать курс",
            width=400,
            options=[ft.dropdown.Option(course) for course in GROUPS_BY_COURSE.keys()],
            value=None
        )
        group_dropdown = ft.Dropdown(
            label="Выбрать группу",
            width=400,
            options=[ft.dropdown.Option(g) for g in available_groups],
            value=None
        )
        add_user_status = ft.Text(color=ft.Colors.GREEN)

        def on_course_change(e):
            selected_course = course_dropdown.value
            if selected_course:
                course_number = selected_course.split()[0]
                filtered_groups = [g for g in available_groups if g.startswith(course_number)]
                group_dropdown.options = [ft.dropdown.Option(g) for g in filtered_groups]
            else:
                group_dropdown.options = [ft.dropdown.Option(g) for g in available_groups]
            group_dropdown.value = None
            group_dropdown.update()  # принудительное обновление dropdown

        course_dropdown.on_change = on_course_change

        async def add_user(e):
            try:
                user_id_str = user_id_field.value.strip()
                if not user_id_str.isdigit():
                    raise ValueError()
                user_id = int(user_id_str)

                selected_course = course_dropdown.value
                group = group_dropdown.value

                if not selected_course:
                    add_user_status.value = "❌ Выберите курс"
                    add_user_status.color = ft.Colors.RED
                    page.update()
                    return

                if not group:
                    add_user_status.value = "❌ Выберите группу"
                    add_user_status.color = ft.Colors.RED
                    page.update()
                    return

                course_number = selected_course.split()[0]
                if not group.startswith(course_number):
                    add_user_status.value = f"❌ Группа должна быть с {course_number} курса"
                    add_user_status.color = ft.Colors.RED
                    page.update()
                    return

                await db.save_user_preference(user_id, group)
                add_user_status.value = f"✅ Пользователь {user_id} добавлен в группу {group}"
                add_user_status.color = ft.Colors.GREEN

                user_id_field.value = ""
                course_dropdown.value = None
                group_dropdown.value = None
                group_dropdown.options = [ft.dropdown.Option(g) for g in available_groups]
                group_dropdown.update()

                page.update()

            except ValueError:
                add_user_status.value = "❌ Некорректный Telegram ID (должно быть число)"
                add_user_status.color = ft.Colors.RED
                page.update()
            except Exception as ex:
                add_user_status.value = f"❌ Ошибка: {str(ex)}"
                add_user_status.color = ft.Colors.RED
                page.update()

        # Добавление новой группы
        new_group_field = ft.TextField(
            label="Название новой группы",
            width=400,
            hint_text="Например: 1пк1, 2ис3, 4бу2"
        )
        schedule_json_field = ft.TextField(
            label="JSON расписания (вставьте сюда)",
            multiline=True,
            min_lines=10,
            max_lines=15,
            width=600,
            hint_text='Пример: {"monday": {"lessons": [...], "date": "22 декабря"}, ...}'
        )
        add_group_status = ft.Text(color=ft.Colors.GREEN)

        async def add_new_group(e):
            group_name_raw = new_group_field.value.strip()
            group_name = group_name_raw.lower()
            json_text = schedule_json_field.value.strip()

            if not group_name_raw or not json_text:
                add_group_status.value = "❌ Заполните все поля"
                add_group_status.color = ft.Colors.RED
                page.update()
                return

            if not GROUP_FORMAT_PATTERN.match(group_name):
                add_group_status.value = "❌ Некорректный формат группы. Пример: 1пк1, 2ис3, 4бу2"
                add_group_status.color = ft.Colors.RED
                page.update()
                return

            try:
                schedule_data = json.loads(json_text)
                week_start = datetime.now().strftime("%Y-%m-%d")
                group_upper = group_name_raw.upper()
                await db.save_schedule(group_upper, schedule_data, week_start)
                add_group_status.value = f"✅ Группа '{group_upper}' добавлена!"
                add_group_status.color = ft.Colors.GREEN

                new_group_field.value = ""
                schedule_json_field.value = ""

                # Обновляем список групп
                nonlocal all_schedules, available_groups
                all_schedules = await db.get_all_schedules()
                available_groups = sorted(all_schedules.keys())

                # Обновляем dropdown
                group_dropdown.options = [ft.dropdown.Option(g) for g in available_groups]
                group_dropdown.update()

                # Если курс выбран — применяем фильтр
                if course_dropdown.value:
                    on_course_change(None)

                page.update()

            except json.JSONDecodeError:
                add_group_status.value = "❌ Ошибка в формате JSON"
                add_group_status.color = ft.Colors.RED
            except Exception as ex:
                add_group_status.value = f"❌ Ошибка: {str(ex)}"
                add_group_status.color = ft.Colors.RED
            page.update()

        # Статистика и БД
        stats_column = ft.Column([])
        db_info_column = ft.Column([])

        table_names_ru = {
            "schedules": "Расписания",
            "sqlite_sequence": "Последовательности SQLite",
            "cache": "Кэш",
            "users": "Пользователи",
            "logs": "Логи"
        }

        def refresh_display():
            stats_column.controls.clear()
            stats_column.controls.extend([
                ft.Text("Статистика бота", size=24),
                ft.Text(f"Всего пользователей: {stats.get('total_users', 0)}"),
                ft.Text(f"Всего запросов расписания: {stats.get('total_requests', 0)}"),
                ft.Text("Популярные группы:", weight=ft.FontWeight.BOLD),
                ft.Column([ft.Text(f"• {g['_id']} — {g['count']} запросов") for g in stats.get('popular_groups', [])] or [ft.Text("Нет данных")])
            ])

            db_info_column.controls.clear()
            db_info_column.controls.extend([
                ft.Text("Информация о базе данных", size=24),
                ft.Text(f"Путь к БД: {info.get('database_path', 'неизвестно')}"),
                ft.Column([ft.Text(f"• {table_names_ru.get(table, table)}: {count} записей") for table, count in info.get('tables', {}).items()])
            ])

            page.update()

        refresh_display()

        async def refresh_stats(e):
            status_text.value = "Обновление статистики..."
            status_text.color = ft.Colors.BLUE
            page.update()

            nonlocal stats, info
            stats = await db.get_statistics()
            info = await db.get_database_info()
            refresh_display()

            status_text.value = "✅ Статистика обновлена!"
            status_text.color = ft.Colors.GREEN
            page.update()

        # Кнопки действий
        action_buttons = ft.Column([
            ft.FilledButton("Обновить расписание", on_click=lambda e: asyncio.create_task(update_schedules()), width=250, style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700)),
            ft.FilledButton("Обновить статистику бота", on_click=refresh_stats, width=250, style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700)),
            ft.FilledButton("Очистить кэш", on_click=lambda e: asyncio.create_task(clear_cache()), width=250, style=ft.ButtonStyle(bgcolor=ft.Colors.RED_700)),
        ], spacing=15)

        # Основной интерфейс
        return ft.Column([
            ft.Row([
                ft.Text("Админ-панель", size=32, weight=ft.FontWeight.BOLD),
                ft.FilledButton("Выйти в логин", on_click=logout, width=200),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(),

            about_project_block,

            ft.Text("Добавить пользователя вручную", size=24),
            user_id_field,
            course_dropdown,
            group_dropdown,
            ft.FilledButton("Добавить пользователя", on_click=add_user, width=400),
            add_user_status,
            ft.Divider(),

            ft.Text("Добавить новую группу и расписание", size=24),
            new_group_field,
            schedule_json_field,
            ft.FilledButton("Добавить группу и расписание", on_click=add_new_group, width=600),
            add_group_status,
            ft.Divider(),

            stats_column,
            ft.Divider(),

            ft.Row([
                db_info_column,
                ft.VerticalDivider(width=40),
                action_buttons
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START),

            ft.Divider(),
            status_text
        ], spacing=20)

    async def update_schedules():
        status_text.value = "Обновление расписаний начато..."
        status_text.color = ft.Colors.BLUE
        page.update()
        count = await preload_all_schedules()
        status_text.value = f"✅ Расписания обновлены! Загружено: {count} групп"
        status_text.color = ft.Colors.GREEN
        page.update()

    async def clear_cache():
        status_text.value = "Очистка кэша..."
        status_text.color = ft.Colors.BLUE
        page.update()
        await db.cleanup_old_data(days_old=1)
        status_text.value = "✅ Кэш очищен!"
        status_text.color = ft.Colors.GREEN
        page.update()

ft.app(target=main)
import flet as ft
from src.database.db import db
from src.bot.preload import preload_all_schedules
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise ValueError("ADMIN_PASSWORD не установлен в .env файле! Добавьте строку ADMIN_PASSWORD=ваш_пароль")

async def main(page: ft.Page):
    page.title = "Админ-панель расписания"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 1100
    page.window_height = 950
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
        groups = sorted(all_schedules.keys())

        user_id_field = ft.TextField(label="Telegram ID пользователя", width=400, hint_text="Например: 123456789")
        group_dropdown = ft.Dropdown(
            label="Выбрать группу",
            width=400,
            options=[ft.dropdown.Option(g) for g in groups]
        )
        add_user_status = ft.Text(color=ft.Colors.GREEN)

        async def add_user(e):
            try:
                user_id = int(user_id_field.value.strip())
                group = group_dropdown.value
                if not group:
                    add_user_status.value = "❌ Выберите группу"
                    add_user_status.color = ft.Colors.RED
                else:
                    await db.save_user_preference(user_id, group)
                    add_user_status.value = f"✅ Пользователь {user_id} добавлен в группу {group}"
                    add_user_status.color = ft.Colors.GREEN
                    user_id_field.value = ""
                page.update()
            except ValueError:
                add_user_status.value = "❌ Некорректный Telegram ID (должно быть число)"
                add_user_status.color = ft.Colors.RED
            except Exception as ex:
                add_user_status.value = f"❌ Ошибка: {str(ex)}"
                add_user_status.color = ft.Colors.RED
            page.update()

        new_group_field = ft.TextField(label="Название новой группы", width=400, hint_text="Например: 4pk2")
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
            group_name = new_group_field.value.strip()
            json_text = schedule_json_field.value.strip()

            if not group_name or not json_text:
                add_group_status.value = "❌ Заполните все поля"
                add_group_status.color = ft.Colors.RED
                page.update()
                return

            try:
                schedule_data = json.loads(json_text)
                week_start = datetime.now().strftime("%Y-%m-%d")
                await db.save_schedule(group_name, schedule_data, week_start)
                add_group_status.value = f"✅ Группа '{group_name}' добавлена!"
                add_group_status.color = ft.Colors.GREEN

                new_group_field.value = ""
                schedule_json_field.value = ""

                all_schedules = await db.get_all_schedules()
                groups = sorted(all_schedules.keys())
                group_dropdown.options = [ft.dropdown.Option(g) for g in groups]
                page.update()

            except json.JSONDecodeError:
                add_group_status.value = "❌ Ошибка в формате JSON"
                add_group_status.color = ft.Colors.RED
            except Exception as ex:
                add_group_status.value = f"❌ Ошибка: {str(ex)}"
                add_group_status.color = ft.Colors.RED
            page.update()

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

        action_buttons = ft.Column([
            ft.FilledButton(
                "Обновить расписание",
                on_click=lambda e: asyncio.create_task(update_schedules()),
                width=250,
                style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700)
            ),
            ft.FilledButton(
                "Обновить статистику бота",
                on_click=refresh_stats,
                width=250,
                style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700)
            ),
            ft.FilledButton(
                "Очистить кэш",
                on_click=lambda e: asyncio.create_task(clear_cache()),
                width=250,
                style=ft.ButtonStyle(bgcolor=ft.Colors.RED_700)
            ),
        ], spacing=15)

        return ft.Column([
            ft.Row([
                ft.Text("Админ-панель", size=32, weight=ft.FontWeight.BOLD),
                ft.FilledButton("Выйти в логин", on_click=logout, width=200)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(),

            ft.Text("Добавить пользователя вручную", size=24),
            user_id_field,
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

ft.app(target=main, port=8000)
import aiosqlite
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
from dotenv import load_dotenv
from pathlib import Path
from src.utils.logger import log

load_dotenv()

class SQLiteDatabase:
    """
    Класс для работы с SQLite базой данных.
    Реализует паттерн Singleton для подключения к базе данных.
    """
    
    _instance: Optional['SQLiteDatabase'] = None
    _db: Optional[aiosqlite.Connection] = None
    _db_path: str = ""  # Будет установлен в connect()
    _is_connected: bool = False
    
    def __new__(cls) -> 'SQLiteDatabase':
        if cls._instance is None:
            cls._instance = super(SQLiteDatabase, cls).__new__(cls)
        return cls._instance
    
    async def connect(self) -> None:
        """Подключение к базе данных в папке data/"""
        if not self._is_connected or self._db is None:
            # Определяем путь: корень проекта / data / schedule_bot.db
            project_root = Path(__file__).resolve().parent.parent.parent
            data_dir = project_root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)  # Создаём папку, если нет
            
            db_path = data_dir / "schedule_bot.db"
            self._db_path = str(db_path)  # Сохраняем путь для info
            
            self._db = await aiosqlite.connect(self._db_path)
            self._db.row_factory = aiosqlite.Row
            self._is_connected = True
            await self._create_tables()
            log.info(f"✅ Подключение к SQLite установлено: {self._db_path}")
    
    def _ensure_connected(self) -> aiosqlite.Connection:
        if self._db is None or not self._is_connected:
            raise ConnectionError("База данных не подключена. Сначала вызовите connect()")
        return self._db
    
    async def _create_tables(self) -> None:
        db = self._ensure_connected()
        
        await db.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL,
            week_start TEXT NOT NULL,
            schedule_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            UNIQUE(group_name, week_start)
        )
        ''')
        
        await db.execute('''
        CREATE TABLE IF NOT EXISTS cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL UNIQUE,
            data TEXT NOT NULL,
            cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expire_at TIMESTAMP,
            CHECK(expire_at > cached_at)
        )
        ''')
        
        await db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            group_name TEXT NOT NULL,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        await db.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            group_name TEXT NOT NULL,
            day TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT DEFAULT 'telegram_bot'
        )
        ''')
        
        await db.execute('CREATE INDEX IF NOT EXISTS idx_schedules_group ON schedules(group_name, is_active)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_cache_group ON cache(group_name)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_users_id ON users(user_id)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_cache_expire ON cache(expire_at)')
        
        await db.commit()
        print("✅ Таблицы базы данных созданы/проверены")
    
    async def save_schedule(self, group_name: str, schedule_data: Dict, week_start: str) -> int:
        """
        Сохраняет расписание группы в базу данных.
        
        Args:
            group_name (str): Название группы
            schedule_data (Dict): Данные расписания
            week_start (str): Начало недели (для идентификации)
            
        Returns:
            int: ID сохраненной записи
        """
        await self.connect()
        db = self._ensure_connected()
        
        try:
            # Конвертируем словарь в JSON строку
            schedule_json = json.dumps(schedule_data, ensure_ascii=False)
            
            # Вставляем или обновляем запись
            await db.execute('''
            INSERT OR REPLACE INTO schedules 
            (group_name, week_start, schedule_data, updated_at, is_active)
            VALUES (?, ?, ?, ?, 1)
            ''', (group_name, week_start, schedule_json, datetime.utcnow()))
            
            await db.commit()
            
            # Также сохраняем в кэш
            await self.save_to_cache(group_name, schedule_data)
            
            print(f"✅ Расписание для группы {group_name} сохранено в SQLite")
            
            # Получаем ID вставленной записи
            cursor = await db.execute('SELECT last_insert_rowid()')
            result = await cursor.fetchone()
            return result[0] if result else 0
            
        except Exception as e:
            print(f"❌ Ошибка сохранения расписания: {e}")
            raise
    
    async def get_schedule(self, group_name: str, week_start: Optional[str] = None) -> Optional[Dict]:
        """
        Получает расписание группы из базы данных.
        
        Args:
            group_name (str): Название группы
            week_start (str, optional): Начало недели
            
        Returns:
            Optional[Dict]: Данные расписания или None
        """
        await self.connect()
        db = self._ensure_connected()
        
        try:
            # Сначала проверяем кэш
            cached = await self.get_from_cache(group_name)
            if cached:
                print(f"📦 Используем кэшированные данные для {group_name}")
                return cached
            
            # Ищем в основном хранилище
            query = '''
            SELECT schedule_data FROM schedules 
            WHERE group_name = ? AND is_active = 1
            '''
            params = [group_name]
            
            if week_start:
                query += ' AND week_start = ?'
                params.append(week_start)
            
            query += ' ORDER BY updated_at DESC LIMIT 1'
            
            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
            
            if row:
                # Конвертируем JSON строку обратно в словарь
                schedule_data = json.loads(row['schedule_data'])
                
                # Сохраняем в кэш
                await self.save_to_cache(group_name, schedule_data)
                
                return schedule_data
            
            return None
            
        except Exception as e:
            print(f"❌ Ошибка получения расписания: {e}")
            return None
    
    async def save_to_cache(self, group_name: str, schedule_data: Dict, ttl_hours: int = 1) -> None:
        """
        Сохраняет данные в кэш с TTL (время жизни).
        
        Args:
            group_name (str): Название группы
            schedule_data (Dict): Данные расписания
            ttl_hours (int): Время жизни кэша в часах
        """
        await self.connect()
        db = self._ensure_connected()
        
        try:
            expire_at = datetime.utcnow() + timedelta(hours=ttl_hours)
            data_json = json.dumps(schedule_data, ensure_ascii=False)
            
            await db.execute('''
            INSERT OR REPLACE INTO cache 
            (group_name, data, cached_at, expire_at)
            VALUES (?, ?, ?, ?)
            ''', (group_name, data_json, datetime.utcnow(), expire_at))
            
            await db.commit()
            
        except Exception as e:
            print(f"❌ Ошибка сохранения в кэш: {e}")
    
    async def get_from_cache(self, group_name: str) -> Optional[Dict]:
        """
        Получает данные из кэша.
        
        Args:
            group_name (str): Название группы
            
        Returns:
            Optional[Dict]: Данные из кэша или None
        """
        await self.connect()
        db = self._ensure_connected()
        
        try:
            cursor = await db.execute('''
            SELECT data FROM cache 
            WHERE group_name = ? AND expire_at > ?
            ''', (group_name, datetime.utcnow()))
            
            row = await cursor.fetchone()
            
            if row:
                return json.loads(row['data'])
            
            return None
            
        except Exception as e:
            print(f"❌ Ошибка получения из кэша: {e}")
            return None
    
    async def save_user_preference(self, user_id: int, group_name: str) -> None:
        """
        Сохраняет предпочтения пользователя.
        
        Args:
            user_id (int): ID пользователя в Telegram
            group_name (str): Выбранная группа
        """
        await self.connect()
        db = self._ensure_connected()
        
        try:
            await db.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, group_name, last_activity, updated_at)
            VALUES (?, ?, ?, ?)
            ''', (user_id, group_name, datetime.utcnow(), datetime.utcnow()))
            
            await db.commit()
            
            print(f"✅ Предпочтения пользователя {user_id} сохранены")
            
        except Exception as e:
            print(f"❌ Ошибка сохранения предпочтений: {e}")
    
    async def get_user_group(self, user_id: int) -> Optional[str]:
        """
        Получает сохраненную группу пользователя.
        
        Args:
            user_id (int): ID пользователя в Telegram
            
        Returns:
            Optional[str]: Название группы или None
        """
        await self.connect()
        db = self._ensure_connected()
        
        try:
            cursor = await db.execute(
                'SELECT group_name FROM users WHERE user_id = ?',
                (user_id,)
            )
            
            row = await cursor.fetchone()
            return row['group_name'] if row else None
            
        except Exception as e:
            print(f"❌ Ошибка получения группы пользователя: {e}")
            return None
    
    async def log_request(self, user_id: int, group_name: str, day: str) -> None:
        """
        Логирует запросы пользователей.
        
        Args:
            user_id (int): ID пользователя
            group_name (str): Запрошенная группа
            day (str): Запрошенный день
        """
        await self.connect()
        db = self._ensure_connected()
        
        try:
            await db.execute('''
            INSERT INTO logs (user_id, group_name, day, timestamp)
            VALUES (?, ?, ?, ?)
            ''', (user_id, group_name, day, datetime.utcnow()))
            
            await db.commit()
            
        except Exception as e:
            print(f"❌ Ошибка логирования: {e}")
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Получает статистику использования бота.
        
        Returns:
            Dict: Статистические данные
        """
        await self.connect()
        db = self._ensure_connected()
        
        try:
            # Всего пользователей
            cursor = await db.execute('SELECT COUNT(DISTINCT user_id) as count FROM users')
            row = await cursor.fetchone()
            total_users = row['count'] if row and 'count' in row else 0
            
            # Всего запросов
            cursor = await db.execute('SELECT COUNT(*) as count FROM logs')
            row = await cursor.fetchone()
            total_requests = row['count'] if row and 'count' in row else 0
            
            # Самые популярные группы
            cursor = await db.execute('''
            SELECT group_name, COUNT(*) as count 
            FROM logs 
            GROUP BY group_name 
            ORDER BY count DESC 
            LIMIT 5
            ''')
            
            popular_groups = []
            async for row in cursor:
                if row and 'group_name' in row and 'count' in row:
                    popular_groups.append({
                        '_id': row['group_name'],
                        'count': row['count']
                    })
            
            return {
                'total_users': total_users,
                'total_requests': total_requests,
                'popular_groups': popular_groups
            }
            
        except Exception as e:
            print(f"❌ Ошибка получения статистики: {e}")
            return {}
    
    async def cleanup_old_data(self, days_old: int = 30) -> None:
        """
        Удаляет старые данные.
        
        Args:
            days_old (int): Удалять данные старше N дней
        """
        await self.connect()
        db = self._ensure_connected()
        
        try:
            # Удаляем старые логи
            cursor = await db.execute(
                'DELETE FROM logs WHERE timestamp < datetime("now", ?)',
                (f"-{days_old} days",)
            )
            deleted_logs = cursor.rowcount
            
            # Деактивируем старые расписания
            cursor = await db.execute('''
            UPDATE schedules 
            SET is_active = 0 
            WHERE updated_at < datetime("now", ?) AND is_active = 1
            ''', (f"-{days_old} days",))
            
            deactivated_schedules = cursor.rowcount
            
            # Удаляем просроченный кэш
            cursor = await db.execute(
                'DELETE FROM cache WHERE expire_at < ?',
                (datetime.utcnow(),)
            )
            deleted_cache = cursor.rowcount
            
            await db.commit()
            
            print(f"🧹 Очистка данных: удалено {deleted_logs} логов, "
                  f"деактивировано {deactivated_schedules} расписаний, "
                  f"удалено {deleted_cache} кэшей")
            
        except Exception as e:
            print(f"❌ Ошибка очистки данных: {e}")
    
    async def get_database_info(self) -> Dict[str, Any]:
        """
        Получает информацию о базе данных.
        
        Returns:
            Dict: Информация о БД
        """
        await self.connect()
        db = self._ensure_connected()
        
        try:
            info = {
                'database_path': self._db_path,
                'tables': {}
            }
            
            # Получаем информацию о каждой таблице
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row['name'] async for row in cursor]
            
            for table in tables:
                cursor = await db.execute(f"SELECT COUNT(*) as count FROM {table}")
                row = await cursor.fetchone()
                info['tables'][table] = row['count'] if row else 0
            
            return info
            
        except Exception as e:
            print(f"❌ Ошибка получения информации о БД: {e}")
            return {}
    
    async def close(self) -> None:
        """Закрытие подключения к базе данных"""
        if self._db and self._is_connected:
            await self._db.close()
            self._db = None
            self._is_connected = False
            print("🔌 Подключение к SQLite закрыто")

# Создаем глобальный экземпляр базы данных
db = SQLiteDatabase()
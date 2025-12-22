import logging
from pathlib import Path

# Создаём папку logs, если её нет
log_dir = Path("logs")
log_dir.mkdir(parents=True, exist_ok=True)

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,  # INFO — достаточно для основных событий
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_dir / "bot.log", encoding="utf-8"),
        logging.StreamHandler()  # Чтобы и в консоль выводилось
    ]
)

log = logging.getLogger("schedule_bot")

# Тестовое сообщение — удали, если не нужно
log.info("🔧 Логгер успешно инициализирован")
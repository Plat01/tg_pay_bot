# Исправления для запуска бота

## Проблема

Бот не мог подключиться к Telegram API через SOCKS5 прокси при запуске в Docker.

### Ошибки:
1. `ModuleNotFoundError: No module named 'httpx'` - зависимость httpx не устанавливалась корректно
2. `TypeError: BaseSession.__init__() got an unexpected keyword argument 'connector'` - неправильный API aiogram 3.x

## Решение

### 1. `pyproject.toml` - без изменений

Зависимость `httpx[socks]` была в оригинале, но не использовалась. Aiogram 3.26 имеет встроенную поддержку прокси через `AiohttpSession(proxy=...)`.

### 2. `src/bot/bot.py` - добавлена поддержка прокси

```python
"""Bot initialization and setup."""

import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from src.config import settings
from src.handlers import register_handlers

logger = logging.getLogger(__name__)

proxy_url = settings.proxy_url or os.environ.get("ALL_PROXY") or os.environ.get("all_proxy")

if proxy_url:
    logger.info(f"Using proxy: {proxy_url[:30]}***")
    session = AiohttpSession(proxy=proxy_url)
    bot = Bot(token=settings.bot_token, session=session)
else:
    logger.info("Running without proxy")
    bot = Bot(token=settings.bot_token)
dp = Dispatcher()

register_handlers(dp)
```

### 3. `src/config.py` - добавлена настройка proxy_url

```python
# Application
debug: bool = False
proxy_url: str = ""
```

### 4. `docker-compose.yml` - добавлен network_mode: host

```yaml
services:
  app:
    network_mode: host
    environment:
      - ALL_PROXY=socks5://127.0.0.1:10810
```

### 5. `src/main.py` - настройка логирования до импортов

```python
from src.config import settings

# Configure logging BEFORE imports that use logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from aiogram.enums import ParseMode
from src.bot.bot import bot, dp
```

### 6. `.env.example` - добавлен пример PROXY_URL

```
PROXY_URL=http://user:password@host:port
```

## Результат

Бот успешно запускается и отправляет уведомление админу о перезапуске:
```
Restart notification sent to admin 286018052
```
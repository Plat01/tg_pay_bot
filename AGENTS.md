# Telegram Pay Bot

Асинхронный Telegram бот с aiogram 3.x, SQLModel и PostgreSQL.

## Технологии

- Python 3.12+
- aiogram 3.x (aiohttp-based, прокси через `AiohttpSession(proxy=...)`)
- SQLModel + asyncpg
- Docker + docker-compose
- UV (менеджер зависимостей)

## Code Style

- Использовать комментарии в коде
- Типизация: strict mode
- Асинхронный код везде



## Commits

Автоматически коммить изменения после завершения задачи:

1. Проверь `git status` и `git diff`
2. Используй формат: `<type>: <description>`
   - `feat:` - новая функциональность
   - `fix:` - исправление бага
   - `refactor:` - рефакторинг
   - `docs:` - документация
   - `chore:` - вспомогательные изменения
3. Описание на русском языке
4. НЕ коммить: `.env`, секреты, credentials

## Структура проекта

```
src/
├── bot/           # Инициализация бота
├── handlers/      # Обработчики команд
├── models/        # SQLModel модели
├── repositories/  # Слой доступа к данным
├── services/      # Бизнес-логика
├── db/            # Сессии БД
└── config.py      # Pydantic Settings
```
# План реализации Telegram бота

## Обзор проекта

Создание асинхронного Telegram бота с регистрацией пользователей через команду `/start` с использованием современного стека технологий.

## Технологический стек

| Компонент | Технология | Версия |
|-----------|------------|--------|
| Python | Python | 3.12+ |
| Telegram Bot | aiogram | 3.x |
| ORM | SQLModel | 0.0.x |
| База данных | PostgreSQL | 16 |
| Миграции | Alembic | latest |
| Конфигурация | pydantic-settings | 2.x |
| Менеджер зависимостей | UV | latest |
| Контейнеризация | Docker + docker-compose | latest |

## Структура проекта

```
tg_pay_bot/
├── .kilocodeignore          # Игнорируемые файлы для KiloCode
├── .kilocoderules           # Правила проекта для KiloCode
├── .env.example             # Пример переменных окружения
├── .python-version          # Версия Python для UV
├── pyproject.toml           # Конфигурация проекта и зависимости
├── uv.lock                  # Lock-файл зависимостей (генерируется)
├── Dockerfile               # Docker-образ приложения
├── docker-compose.yml       # Оркестрация сервисов
├── alembic.ini              # Конфигурация Alembic
├── alembic/                 # Миграции базы данных
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── src/
│   ├── __init__.py
│   ├── main.py              # Точка входа
│   ├── config.py            # Конфигурация (pydantic-settings)
│   ├── bot/
│   │   ├── __init__.py
│   │   └── bot.py           # Инициализация бота
│   ├── handlers/
│   │   ├── __init__.py
│   │   └── start.py         # Хендлер /start
│   ├── models/
│   │   ├── __init__.py
│   │   └── user.py          # Модель пользователя
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base.py          # Базовый репозиторий
│   │   └── user.py          # Репозиторий пользователя
│   ├── services/
│   │   ├── __init__.py
│   │   └── user.py          # Сервис пользователя
│   └── db/
│       ├── __init__.py
│       └── session.py       # Сессия БД
└── README.md                # Документация проекта
```

## Файлы для создания

### 1. Конфигурационные файлы

#### .kilocodeignore
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
.venv/
venv/
ENV/
env/

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/
.nox/

# Type checking
.mypy_cache/
.dmypy.json
dmypy.json

# Database
*.db
*.sqlite3

# Logs
*.log
logs/

# Environment
.env
.env.local
.env.*.local

# Docker
.docker/

# UV
.uv/

# Alembic
alembic/versions/*.pyc
```

#### .kilocoderules
```
# Правила проекта Telegram бота

## Технологический стек
- Python 3.12+
- aiogram 3.x для Telegram бота
- SQLModel для ORM (на базе SQLAlchemy 2.0 + Pydantic v2)
- PostgreSQL 16
- Alembic для миграций
- pydantic-settings для конфигурации
- UV как менеджер зависимостей

## Архитектура
- Разделение по слоям: handlers -> services -> repositories -> models
- Асинхронный код везде (async/await)
- Type hints для всех функций
- Docstrings для классов и публичных методов

## Стиль кода
- Использовать asyncpg для асинхронного подключения к PostgreSQL
- Все модели наследуются от SQLModel
- Конфигурация через pydantic-settings с .env файлом
- Логирование через logging модуль

## Docker
- Использовать multi-stage build для оптимизации размера
- Не запускать от root пользователя
- Использовать healthcheck для БД

## Миграции
- Все изменения схемы БД через Alembic
- Автогенерация миграций: alembic revision --autogenerate -m "description"
- Применение: alembic upgrade head
```

#### .env.example
```
# Telegram Bot
BOT_TOKEN=your_bot_token_here

# Database
DB_HOST=db
DB_PORT=5432
DB_NAME=tg_pay_bot
DB_USER=postgres
DB_PASSWORD=postgres

# Optional
DEBUG=false
```

#### .python-version
```
3.12
```

#### pyproject.toml
```toml
[project]
name = "tg-pay-bot"
version = "0.1.0"
description = "Async Telegram bot with user registration"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "aiogram>=3.4.0",
    "sqlmodel>=0.0.16",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "pydantic-settings>=2.1.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.2.0",
    "mypy>=1.8.0",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
ignore = []

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### 2. Docker файлы

#### Dockerfile
```dockerfile
# Build stage
FROM python:3.12-slim as builder

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies
RUN uv pip install --system --no-cache -e .

# Production stage
FROM python:3.12-slim

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Run the application
CMD ["python", "-m", "src.main"]
```

#### docker-compose.yml
```yaml
services:
  app:
    build: .
    container_name: tg_pay_bot_app
    restart: unless-stopped
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./src:/app/src:ro  # For development

  db:
    image: postgres:16-alpine
    container_name: tg_pay_bot_db
    restart: unless-stopped
    environment:
      POSTGRES_DB: tg_pay_bot
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### 3. Конфигурация Alembic

#### alembic.ini
```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = driver://user:pass@localhost/dbname

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

#### alembic/env.py
```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from src.config import settings
from src.db.session import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return settings.database_url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

#### alembic/script.py.mako
```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

### 4. Исходный код

#### src/__init__.py
```python
"""Telegram Pay Bot package."""
```

#### src/config.py
```python
"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Telegram Bot
    bot_token: str

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "tg_pay_bot"
    db_user: str = "postgres"
    db_password: str = "postgres"

    # Application
    debug: bool = False

    @property
    def database_url(self) -> str:
        """Build async database URL for PostgreSQL."""
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
```

#### src/db/__init__.py
```python
"""Database package."""
```

#### src/db/session.py
```python
"""Database session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


# Base class for models
from sqlmodel import SQLModel

Base = SQLModel
```

#### src/models/__init__.py
```python
"""Models package."""

from src.models.user import User

__all__ = ["User"]
```

#### src/models/user.py
```python
"""User model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, SQLModel

if TYPE_CHECKING:
    pass


class User(SQLModel, table=True):
    """User model representing a Telegram user."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    telegram_id: int = Field(unique=True, index=True)
    username: str | None = Field(default=None, max_length=255)
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    language_code: str | None = Field(default=None, max_length=10)
    is_bot: bool = Field(default=False)
    is_premium: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "telegram_id": 123456789,
                "username": "johndoe",
                "first_name": "John",
                "last_name": "Doe",
                "language_code": "en",
                "is_bot": False,
                "is_premium": False,
            }
        }
```

#### src/repositories/__init__.py
```python
"""Repositories package."""

from src.repositories.user import UserRepository

__all__ = ["UserRepository"]
```

#### src/repositories/base.py
```python
"""Base repository with common CRUD operations."""

from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select

ModelType = TypeVar("ModelType", bound=SQLModel)


class BaseRepository(Generic[ModelType]):
    """Base repository with common database operations."""

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        """Initialize repository with model and session."""
        self.model = model
        self.session = session

    async def create(self, data: dict) -> ModelType:
        """Create a new record."""
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def get_by_id(self, id: int) -> ModelType | None:
        """Get record by ID."""
        return await self.session.get(self.model, id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """Get all records with pagination."""
        statement = select(self.model).offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def update(self, instance: ModelType, data: dict) -> ModelType:
        """Update an existing record."""
        for key, value in data.items():
            setattr(instance, key, value)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def delete(self, instance: ModelType) -> None:
        """Delete a record."""
        await self.session.delete(instance)
        await self.session.commit()
```

#### src/repositories/user.py
```python
"""User repository for database operations."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize user repository."""
        super().__init__(User, session)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Get user by Telegram ID."""
        statement = select(User).where(User.telegram_id == telegram_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Get user by username."""
        statement = select(User).where(User.username == username)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()
```

#### src/services/__init__.py
```python
"""Services package."""

from src.services.user import UserService

__all__ = ["UserService"]
```

#### src/services/user.py
```python
"""User service for business logic."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.repositories.user import UserRepository


class UserService:
    """Service for user-related business logic."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize user service with session."""
        self.repository = UserRepository(session)

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
        is_bot: bool = False,
        is_premium: bool = False,
    ) -> User:
        """Get existing user or create a new one."""
        user = await self.repository.get_by_telegram_id(telegram_id)

        if user:
            # Update user info if changed
            update_data = {}
            if user.username != username:
                update_data["username"] = username
            if user.first_name != first_name:
                update_data["first_name"] = first_name
            if user.last_name != last_name:
                update_data["last_name"] = last_name
            if user.language_code != language_code:
                update_data["language_code"] = language_code
            if user.is_premium != is_premium:
                update_data["is_premium"] = is_premium

            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                user = await self.repository.update(user, update_data)
            return user

        # Create new user
        user_data = {
            "telegram_id": telegram_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "language_code": language_code,
            "is_bot": is_bot,
            "is_premium": is_premium,
        }
        return await self.repository.create(user_data)

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        """Get user by Telegram ID."""
        return await self.repository.get_by_telegram_id(telegram_id)
```

#### src/bot/__init__.py
```python
"""Bot package."""
```

#### src/bot/bot.py
```python
"""Bot initialization and setup."""

from aiogram import Bot, Dispatcher

from src.config import settings
from src.handlers import register_handlers

# Initialize bot and dispatcher
bot = Bot(token=settings.bot_token)
dp = Dispatcher()

# Register all handlers
register_handlers(dp)
```

#### src/handlers/__init__.py
```python
"""Handlers package."""

from aiogram import Dispatcher

from src.handlers.start import register_start_handlers


def register_handlers(dp: Dispatcher) -> None:
    """Register all handlers to dispatcher."""
    register_start_handlers(dp)
```

#### src/handlers/start.py
```python
"""Start command handler for user registration."""

import logging

from aiogram import Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from src.db.session import async_session_maker
from src.services.user import UserService

logger = logging.getLogger(__name__)


async def cmd_start(message: Message) -> None:
    """Handle /start command - register or welcome back user."""
    async with async_session_maker() as session:
        user_service = UserService(session)

        # Get user info from message
        user = message.from_user
        if not user:
            await message.answer("Error: Could not get user info")
            return

        # Register or update user
        db_user = await user_service.get_or_create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code,
            is_bot=user.is_bot,
            is_premium=getattr(user, "is_premium", False),
        )

        # Send welcome message
        if db_user.created_at == db_user.updated_at:
            # New user
            await message.answer(
                f"Welcome, {user.first_name or 'User'}! 🎉\n"
                "You have been successfully registered."
            )
            logger.info(f"New user registered: {user.id} (@{user.username})")
        else:
            # Existing user
            await message.answer(
                f"Welcome back, {user.first_name or 'User'}! 👋"
            )
            logger.info(f"User logged in: {user.id} (@{user.username})")


def register_start_handlers(dp: Dispatcher) -> None:
    """Register start command handlers."""
    dp.message.register(cmd_start, CommandStart())
```

#### src/main.py
```python
"""Main entry point for the Telegram bot."""

import asyncio
import logging

from aiogram.enums import ParseMode

from src.bot.bot import bot, dp
from src.config import settings
from src.db.session import engine
from sqlmodel import SQLModel


async def create_tables() -> None:
    """Create database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def main() -> None:
    """Start the bot."""
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    logger.info("Starting bot...")

    # Create tables (for development; use Alembic in production)
    # await create_tables()

    # Start polling
    try:
        await dp.start_polling(bot, parse_mode=ParseMode.HTML)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
```

### 5. README.md

```markdown
# Telegram Pay Bot

Асинхронный Telegram бот с регистрацией пользователей.

## Технологии

- Python 3.12+
- aiogram 3.x
- SQLModel (SQLAlchemy 2.0 + Pydantic v2)
- PostgreSQL 16
- Alembic (миграции)
- Docker + docker-compose
- UV (менеджер зависимостей)

## Быстрый старт

### 1. Клонирование и настройка

```bash
# Клонировать репозиторий
git clone <repo-url>
cd tg_pay_bot

# Создать .env файл
cp .env.example .env
# Отредактировать .env и добавить BOT_TOKEN
```

### 2. Запуск через Docker

```bash
# Запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f app
```

### 3. Локальная разработка

```bash
# Установить UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Создать виртуальное окружение и установить зависимости
uv venv
source .venv/bin/activate
uv pip install -e .

# Запустить миграции
alembic upgrade head

# Запустить бота
python -m src.main
```

## Миграции базы данных

```bash
# Создать миграцию
alembic revision --autogenerate -m "description"

# Применить миграции
alembic upgrade head

# Откатить последнюю миграцию
alembic downgrade -1
```

## Структура проекта

```
src/
├── bot/           # Инициализация бота
├── handlers/      # Обработчики команд
├── models/        # Модели БД (SQLModel)
├── repositories/  # Слой доступа к данным
├── services/      # Бизнес-логика
├── db/            # Сессии и подключения
├── config.py      # Конфигурация
└── main.py        # Точка входа
```

## Переменные окружения

| Переменная | Описание | Обязательно |
|------------|----------|-------------|
| BOT_TOKEN | Токен Telegram бота | Да |
| DB_HOST | Хост БД | Нет (localhost) |
| DB_PORT | Порт БД | Нет (5432) |
| DB_NAME | Имя БД | Нет (tg_pay_bot) |
| DB_USER | Пользователь БД | Нет (postgres) |
| DB_PASSWORD | Пароль БД | Нет (postgres) |
| DEBUG | Режим отладки | Нет (false) |
```

## Порядок создания файлов

1. Конфигурационные файлы: `.kilocodeignore`, `.kilocoderules`, `.env.example`, `.python-version`, `pyproject.toml`
2. Docker файлы: `Dockerfile`, `docker-compose.yml`
3. Alembic: `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`
4. Исходный код (в порядке зависимостей):
   - `src/__init__.py`
   - `src/config.py`
   - `src/db/__init__.py`, `src/db/session.py`
   - `src/models/__init__.py`, `src/models/user.py`
   - `src/repositories/__init__.py`, `src/repositories/base.py`, `src/repositories/user.py`
   - `src/services/__init__.py`, `src/services/user.py`
   - `src/bot/__init__.py`, `src/bot/bot.py`
   - `src/handlers/__init__.py`, `src/handlers/start.py`
   - `src/main.py`
5. Документация: `README.md`

## Следующие шаги

После создания всех файлов:

1. Выполнить `uv sync` для установки зависимостей
2. Создать файл `.env` с реальным токеном бота
3. Запустить `docker-compose up -d` для старта БД
4. Выполнить `alembic upgrade head` для создания таблиц
5. Запустить бота `python -m src.main`
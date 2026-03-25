# Telegram Pay Bot

Асинхронный Telegram бот с регистрацией пользователей, платежами и реферальной системой.

## Технологии

- Python 3.12+
- aiogram 3.x
- SQLModel (SQLAlchemy 2.0 + Pydantic v2)
- PostgreSQL 16
- Alembic (миграции)
- Docker + docker-compose
- UV (менеджер зависимостей)

## Возможности

- Регистрация пользователей через `/start`
- Реферальная система с уникальными кодами
- Начисление процентов от платежей рефералов
- Платежная система (входящие платежи)

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

# Запустить БД
docker-compose up -d db

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

## Модели данных

### User (Пользователь)
- telegram_id, username, first_name, last_name
- referral_code - уникальный реферальный код
- referred_by_id - ID реферера
- balance - баланс пользователя

### Payment (Платеж)
- user_id, amount, currency
- status - pending/completed/failed/cancelled
- payment_provider, external_id

### ReferralEarning (Реферальное начисление)
- referrer_id, referral_id, payment_id
- amount, percent
- status - pending/paid/cancelled

## Переменные окружения

| Переменная | Описание | Обязательно |
|------------|----------|-------------|
| BOT_TOKEN | Токен Telegram бота | Да |
| DB_HOST | Хост БД | Нет (localhost) |
| DB_PORT | Порт БД | Нет (5432) |
| DB_NAME | Имя БД | Нет (tg_pay_bot) |
| DB_USER | Пользователь БД | Нет (postgres) |
| DB_PASSWORD | Пароль БД | Нет (postgres) |
| REFERRAL_BONUS_PERCENT | Процент от платежа реферала | Нет (10) |
| DEBUG | Режим отладки | Нет (false) |

## Реферальная система

1. При регистрации пользователь получает уникальный реферальный код
2. Новый пользователь может использовать код при `/start code`
3. При платеже реферала, реферер получает процент на баланс

## Разработка

```bash
# Установить dev зависимости
uv pip install -e ".[dev]"

# Запустить линтер
ruff check .

# Запустить type checking
mypy src/
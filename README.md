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
- Платежная система через Platega.io
- Поддержка multiple payment providers (архитектура)

## Быстрый старт

### 1. Клонирование и настройка

```bash
# Клонировать репозиторий
git clone <repo-url>
cd tg_pay_bot

# Создать .env файл
cp .env.example .env
# Отредактировать .env и добавить BOT_TOKEN и PLATEGA_* настройки
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
├── bot/               # Инициализация бота
├── handlers/          # Обработчики команд
│   ├── start.py       # /start команда
│   ├── deposit.py     # /deposit - пополнение баланса
│   └── webhook.py     # Webhook для платежей
├── models/            # Модели БД (SQLModel)
├── repositories/      # Слой доступа к данным
├── services/          # Бизнес-логика
├── infrastructure/    # Внешние интеграции
│   └── payments/      # Платежные провайдеры
│       ├── base.py    # Абстрактный интерфейс
│       ├── platega.py # Platega.io провайдер
│       ├── factory.py # Фабрика провайдеров
│       └── ...
├── db/                # Сессии и подключения
├── config.py          # Конфигурация
└── main.py            # Точка входа
```

## Модели данных

### User (Пользователь)
- telegram_id, username, first_name, last_name
- referral_code - уникальный реферальный код
- referred_by_id - ID реферера
- balance - баланс пользователя

### Payment (Платеж)
- user_id, amount, currency
- status - pending/completed/failed/cancelled/expired
- payment_provider, external_id
- payment_metadata - дополнительные данные

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
| PLATEGA_API_KEY | API ключ Platega | Для платежей |
| PLATEGA_SHOP_ID | ID магазина Platega | Для платежей |
| PLATEGA_WEBHOOK_SECRET | Секрет для webhook | Для платежей |
| PLATEGA_API_URL | URL API Platega | Нет |
| PLATEGA_WEBHOOK_URL | URL для webhook | Для платежей |

## Платежная система

### Platega.io

Интеграция с [Platega.io](https://platega.io) для приема платежей:

- **СБП QR** - быстрая оплата через СБП
- **Банковская карта** - оплата картами РФ
- **Международная карта** - оплата зарубежными картами
- **Криптовалюта** - оплата криптой

Подробная документация: [docs/platega-integration.md](docs/platega-integration.md)

### Использование

```python
from src.infrastructure.payments import (
    PaymentProviderFactory,
    PlategaPaymentMethod,
)
from decimal import Decimal

# Создать провайдера
provider = PaymentProviderFactory.create("platega")

# Создать платеж
result = await provider.create_payment(
    amount=Decimal("1000"),
    currency="RUB",
    description="Account top-up",
    payment_method=PlategaPaymentMethod.SBP_QR,
)

print(f"Payment URL: {result.payment_url}")
```

### Добавление нового провайдера

Архитектура позволяет легко добавлять новые платежные системы:

1. Создать класс, наследующий `PaymentProvider`
2. Зарегистрировать в `PaymentProviderFactory`
3. Добавить конфигурацию в `Settings`

## Реферальная система

1. При регистрации пользователь получает уникальный реферальный код
2. Новый пользователь может использовать код при `/start code`
3. При платеже реферала, реферер получает процент на баланс

## Документация

- [Platega Integration](docs/platega-integration.md) - интеграция с Platega.io
- [Local vs Production](docs/local-vs-production.md) - различия сред
- [Changes Log](docs/CHANGES.md) - история изменений

## Разработка

```bash
# Установить dev зависимости
uv pip install -e ".[dev]"

# Запустить линтер
ruff check .

# Запустить type checking
mypy src/

# Запустить тесты
pytest tests/
```

## Тестирование

### Структура тестов

```
tests/
├── conftest.py              # Общие фикстуры и конфигурация
├── __init__.py
└── infrastructure/
    └── payments/            # Тесты платежной системы
        ├── test_platega.py  # Тесты PlategaProvider
        ├── test_factory.py  # Тесты PaymentProviderFactory
        ├── test_retry.py    # Тесты retry логики
        └── test_schemas.py  # Тесты Pydantic схем
```

### Запуск тестов

```bash
# Запустить все тесты
uv run pytest tests/ -v

# Запустить только тесты платежей
uv run pytest tests/infrastructure/payments/ -v

# Запустить с покрытием
uv run pytest tests/ --cov=src --cov-report=html
```

### Покрытие тестами

| Модуль | Тесты | Описание |
|--------|-------|----------|
| `test_platega.py` | 25 тестов | PlategaProvider: создание платежей, проверка статуса, webhook, маппинг статусов |
| `test_factory.py` | 9 тестов | PaymentProviderFactory: создание провайдеров, регистрация, кеширование |
| `test_retry.py` | 14 тестов | Retry логика: повторные попытки, exponential backoff, timeout |
| `test_schemas.py` | 23 теста | Pydantic модели: валидация, сериализация, парсинг ответов API |

### Примеры тестов

```python
# Тест создания платежа
@pytest.mark.asyncio
async def test_create_payment_success(mock_settings, platega_create_response):
    """Test successful payment creation."""
    provider = PlategaProvider()
    
    result = await provider.create_payment(
        amount=Decimal("1000.00"),
        currency="RUB",
        description="Test payment",
    )
    
    assert result.success is True
    assert result.payment_url is not None

# Тест webhook с проверкой подписи
def test_parse_webhook_valid(mock_settings, platega_webhook_payload):
    """Test parsing valid webhook with signature."""
    provider = PlategaProvider()
    
    signature = generate_signature(platega_webhook_payload)
    headers = {"X-Signature": signature}
    
    result = provider.parse_webhook(
        json.dumps(platega_webhook_payload).encode(),
        headers,
    )
    
    assert result.status == PaymentStatus.COMPLETED
```

## License

MIT
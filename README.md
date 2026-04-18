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

### 3. Перезапуск бота при изменениях

При изменении кода или .env файла:

```bash
# Перезапуск контейнера приложения
docker compose restart app

# Полная пересборка и перезапуск (если изменен Dockerfile или зависимости)
docker compose up -d --build app

# Перезапуск всех сервисов
docker-compose restart
```

При локальной разработке бот перезапускается автоматически при изменении файлов (если используется `--reload`), либо вручную:

```bash
# Остановить бота (Ctrl+C) и запустить заново
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

## Подключение к БД через SSH туннель

Для подключения к удаленной БД через SSH туннель:

```bash
# Создать SSH туннель (пример)
ssh -L 5433:localhost:5432 user@remote-server.com -N

# Подключиться к БД через туннель
psql -h localhost -p 5433 -U postgres -d tg_pay_bot
```

Опции SSH:
- `-L local_port:remote_host:remote_port` - проброс портов
- `-N` - не открывать shell сессию
- `-f` - запуск в фоне (опционально)

Для постоянного туннеля можно использовать `autossh` или systemd сервис.

## Структура проекта

```
src/
├── bot/                      # Telegram бот
│   ├── handlers/             # Обработчики команд и сообщений
│   │   ├── payment.py        # Обработчики оплаты подписки
│   │   ├── start.py          # Обработчики start и главного меню
│   │   ├── deposit.py        # Обработчики пополнения баланса
│   │   └── admin.py          # Административные обработчики
│   ├── bot.py                # Инициализация бота и диспетчера
│   ├── keyboards.py          # Клавиатуры (inline/reply)
│   ├── texts.py              # Тексты сообщений
│   ├── constants.py          # Константы бота
│   └── subscription_prices.py # Цены и длительность тарифов
├── infrastructure/           # Инфраструктурный слой
│   ├── database/             # Работа с БД
│   │   ├── repositories/      # Репозитории для доступа к данным
│   │   └── session.py         # Сессии БД
│   └── payments/              # Интеграции с платежными системами
│       ├── base.py            # Базовый класс платежной системы
│       ├── platega.py         # Интеграция с Platega
│       ├── factory.py         # Фабрика платежных систем
│       ├── schemas.py         # Pydantic схемы для платежей
│       └── exceptions.py      # Исключения платежных систем
├── models/                   # SQLModel модели (User, Payment, Subscription, etc.)
├── services/                 # Бизнес-логика (payment, user, subscription, referral)
├── workers/                  # Фоновые задачи (scheduler)
├── config.py                 # Конфигурация через pydantic-settings
└── main.py                   # Точка входа
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

### Subscription (Подписка)
- user_id - ID пользователя
- product_id - ID продукта
- is_active - активна ли подписка
- start_date, end_date - период действия

### Product (Продукт)
- subscription_type - тип подписки (trial, monthly, quarterly, yearly)
- price - цена
- duration_days - длительность в днях
- device_limit - лимит устройств
- happ_link - ссылка для подключения

### ReferralEarning (Реферальное начисление)
- referrer_id, referral_id, payment_id
- amount, percent
- status - pending/paid/cancelled

## Переменные окружения

| Переменная | Описание | Обязательно |
|------------|----------|-------------|
| BOT_TOKEN | Токен Telegram бота | Да |
| BOT_LINK | Ссылка на бота (https://t.me/botname) | Да |
| BOT_NAME | Имя бота | Да |
| SUPPORT_LINK | Ссылка на поддержку | Нет |
| PRIVACY_POLICY_LINK | Ссылка на политику конфиденциальности | Нет |
| USER_AGREEMENT_LINK | Ссылка на пользовательское соглашение | Нет |
| DB_HOST | Хост БД | Нет (db в Docker) |
| DB_PORT | Порт БД | Нет (5432) |
| DB_NAME | Имя БД | Нет (tg_pay_bot) |
| DB_USER | Пользователь БД | Нет (postgres) |
| DB_PASSWORD | Пароль БД | Нет (postgres) |
| REFERRAL_BONUS_PERCENT | Процент от платежа реферала | Нет (10) |
| REFERRAL_CODE_LENGTH | Длина реферального кода | Нет (8) |
| ADMIN_IDS | ID администраторов через запятую | Нет |
| DEBUG | Режим отладки | Нет (false) |
| PROXY_URL | URL прокси для бота | Нет |
| DEFAULT_PAYMENT_PROVIDER | Платежный провайдер по умолчанию | Нет (platega) |
| PLATEGA_MERCHANT_ID | ID мерчанта Platega | Для платежей |
| PLATEGA_SECRET | API секрет Platega | Для платежей |
| PLATEGA_API_URL | URL API Platega | Нет |
| PLATEGA_WEBHOOK_URL | URL для webhook | Для платежей |
| PLATEGA_WEBHOOK_SECRET | Секрет для webhook | Для платежей |

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
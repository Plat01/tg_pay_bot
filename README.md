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
docker compose up -d

# Просмотр логов
docker compose logs -f app
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
│   │   ├── admin.py          # Административные обработчики
│   │   └── tariff_admin.py   # Команды /tariffs и /add_tariff
│   ├── bot.py                # Инициализация бота и диспетчера
│   ├── keyboards.py          # Клавиатуры (inline/reply)
│   ├── texts.py              # Тексты сообщений
│   └── constants.py          # Константы бота
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
│   └── tariff.py             # Тарифы: кэш над таблицей tariff_settings и дефолты TARIFFS
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

### TariffSetting (Тариф)
- tariff_type - код тарифа (trial, monthly, ...)
- price, days - цена и длительность
- devices - лимит устройств
- duration_text, label - тексты для кнопок и карточек
- max_grant_days - граница ручной выдачи дней
- is_active - показывать ли тариф в меню оплаты

### ReferralEarning (Реферальное начисление)
- referrer_id, referral_id, payment_id
- amount, percent
- status - pending/paid/cancelled

## Тарифы

Тарифы хранятся в таблице `tariff_settings` и меняются админом прямо из бота:

| Команда | Что делает |
|---------|------------|
| `/tariffs` | Список тарифов, изменение цены, длительности, устройств, текстов, включение/выключение и удаление |
| `/add_tariff` | Создание нового тарифа (код → цена → дни → устройства → тексты) |

Изменения применяются сразу: кэш тарифов перечитывается после каждой правки, перезапуск бота не нужен.

Значения по умолчанию лежат в словаре `TARIFFS` в `src/services/tariff.py`. Они засеиваются
в пустую таблицу при первом старте бота и служат запасным вариантом, пока кэш не загружен:

```python
TARIFFS = {
    "monthly": {
        "price": 199.0,            # цена в рублях (должна быть уникальной)
        "days": 30,                # длительность подписки в днях
        "max_grant_days": 29,      # верхняя граница ручной выдачи дней для этого тарифа
        "duration_text": "1 месяц",  # текст в кнопке и списке тарифов
        "devices": 2,              # лимит устройств (идёт в VPN-подписку)
        "label": "Месячная",       # название типа подписки
    },
    ...
}
```

Из тарифа выводятся длительность подписки и TTL VPN-ключа, лимит устройств, подписи кнопок,
текст выбора тарифа и названия типов подписки.

Ограничения, о которых стоит помнить:

- **Цены должны быть уникальными.** Платежи, созданные до появления метаданных о тарифе,
  сопоставляются по сумме. Бот не даст поставить занятую цену.
- Новые платежи хранят `tariff_type` и `tariff_days` в `payment_metadata`, поэтому смена цены
  или длительности не ломает уже выставленные счета — пользователь получит то, что выбирал.
- Изменения не затрагивают уже выданные подписки: у них своя дата окончания.
- Тариф `trial` удалить нельзя — он используется при выдаче тестового периода.
- Тариф, который больше не продаётся, лучше выключать (пункт 7 в `/tariffs`), а не удалять:
  выключенный исчезает из меню оплаты, но названия в карточках подписок сохраняются.

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
| PLATEGA_ENABLED_METHODS | Коды доступных способов оплаты Platega | Нет (2,11) |
| PAYMENT_PROVIDER_CHECK_TIMEOUT | Таймаут проверки провайдера при старте, сек | Нет (5.0) |
| PAYMENT_METHOD_PROBE_AMOUNT | Сумма пробной транзакции для проверки способа | Нет (10) |

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

### Доступные способы оплаты

При старте бот опрашивает все зарегистрированные платежные провайдеры и
показывает кнопки только тех способов оплаты, которые реально работают
(`PaymentMethodsService`). Проверка идет в три шага:

1. заданы ли учетные данные провайдера (`is_configured()`);
2. отвечает ли его API (`check_availability()`);
3. работает ли каждый отдельный способ оплаты (`check_method_availability()`).

Третий шаг нужен потому, что у мерчанта может быть включена только часть
способов. Platega не отдает этот список через API, поэтому `PlategaProvider`
на каждый способ создает пробную транзакцию на `PAYMENT_METHOD_PROBE_AMOUNT`
рублей: если API отвечает ошибкой — способ выключен. Пробная транзакция не
сохраняется в БД, не оплачивается и истекает на стороне Platega сама.

Проверяются только способы, перечисленные в `PLATEGA_ENABLED_METHODS` (коды
через запятую: `2` — СБП QR, `3` — ЕРИП, `11` — карта РФ, `12` —
международная карта, `13` — криптовалюта). То есть переменная задает список
кандидатов, а окончательный набор кнопок определяет проверка.

### Типы способов оплаты и приоритет провайдеров

Кнопка соответствует **типу** способа оплаты (`PaymentMethodKind`: `sbp`,
`card_ru`, `card_intl`, `erip`, `crypto`), а не конкретному провайдеру. Если
один и тот же тип поддерживают несколько провайдеров, пользователь видит одну
кнопку, а провайдер выбирается в момент нажатия. Если тип не дает ни один
подключенный провайдер — кнопка не показывается вовсе.

**TODO:** приоритет провайдеров пока не настраивается. Сейчас первым идет
`DEFAULT_PAYMENT_PROVIDER`, остальные — в порядке регистрации в фабрике
(заглушка `PaymentMethodsService.get_provider_priority()`). Подробности и план
работ: [.kilo/todo.md](.kilo/todo.md).

Если ни один способ недоступен, внешние способы оплаты не показываются:
остается только оплата с баланса, а админам при перезапуске приходит
предупреждение со списком доступных способов. Кнопки из старых сообщений
проверяются повторно в момент нажатия, поэтому оплата через отключенный
способ не начнется.

Формат callback data: `payment_method:{kind}:{tariff_type}` для подписки и
`method:{kind}` для пополнения баланса. Старые форматы с кодом провайдера
(`payment_method:{provider}:{code}:{tariff_type}`) продолжают работать.

### Добавление нового провайдера

Архитектура позволяет легко добавлять новые платежные системы:

1. Создать класс, наследующий `PaymentProvider`
2. Реализовать `get_payment_methods()` — вернуть способы с их типом
   (`PaymentMethodKind`); при необходимости переопределить `is_configured()`,
   `check_availability()` и `check_method_availability()` — кнопки появятся
   автоматически
3. Зарегистрировать в `PaymentProviderFactory`
4. Добавить конфигурацию в `Settings`

## Логи и диагностика платежей

### Просмотр логов

```bash
# Логи приложения вживую
docker compose logs -f app

# Последние 200 строк
docker compose logs app --tail 200

# Логи БД
docker compose logs db --tail 100

# Логи за период
docker compose logs app --since 30m
docker compose logs app --since 2026-09-16T10:00:00
```

### Почему не прошел платеж

Причина отказа **не сохраняется в БД** — искать нужно в логах и в панели Platega.

**1. Статус платежа через админские команды бота:**

```
/payments <telegram_id>        # платежи юзера: сумма, статус, провайдер, даты
/payment_by_ext <external_id>  # найти юзера по id транзакции Platega
```

**2. Поиск по логам:**

```bash
# По конкретному платежу
docker compose logs app | grep "payment_id=<uuid>"
docker compose logs app | grep "external_id=<platega_id>"

# Ошибки платежной системы
docker compose logs app | grep -iE "Platega create payment failed|connection error|Failed to deliver|Invalid webhook|signature"

# Настоящий статус, который вернула Platega
docker compose logs app | grep "external_status="
```

Ключевые точки логирования:

| Файл | Что логируется |
|------|----------------|
| `src/infrastructure/payments/platega.py` | HTTP-код и текст ошибки при создании платежа, ошибки сети/таймауты, распарсенный webhook |
| `src/services/payment.py` | `external_status` от провайдера и во что он смапился, смена статуса |
| `src/bot/handlers/payment.py` | сбой выдачи VPN уже после успешной оплаты |

**3. Запрос в БД:**

```bash
docker compose exec db psql -U postgres -d tg_pay_bot -c "
select p.id, p.external_id, p.amount, p.status, p.payment_provider,
       p.payment_metadata, p.created_at, p.completed_at, u.telegram_id
from payments p join users u on u.id = p.user_id
where u.telegram_id = '<telegram_id>'
order by p.created_at desc limit 20;"
```

**4. Панель Platega** — окончательный ответ «почему банк отклонил» есть только там, искать по `external_id`.

### Важные нюансы

- Статус `failed` ставится **только** при `CHARGEBACKED`. Любой незнакомый статус Platega маппится в `PENDING` (см. `_map_platega_status_str`), поэтому неудачный платеж чаще всего выглядит как вечный `pending`, а не `failed`. Реальный статус — в логах по `external_status=`.
- Пользователю при `failed` показывается захардкоженный текст «Техническая ошибка платежной системы» — это константа, а не диагноз.

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
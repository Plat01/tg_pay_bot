# Telegram Pay Bot

Асинхронный Telegram бот с aiogram 3.x, SQLModel и PostgreSQL.

## Технологии

- Python 3.12+
- aiogram 3.x (aiohttp-based, прокси через `AiohttpSession(proxy=...)`)
- SQLModel + asyncpg
- Docker + docker-compose
- UV (менеджер зависимостей)

## Общение с пользователем

- Общаться с пользователем на русском языке
- Отвечать кратко и по делу
- Не использовать эмодзи без необходимости

## Code Style

- Использовать комментарии в коде
- Типизация: strict mode
- Асинхронный код везде

## Commits

**ВАЖНО:** Коммитить, проверять, компилировать и пушить код только когда пользователь явно просит об этом!

НЕ делать автоматические коммиты после завершения задачи!

Перед  каждым коммитом описывать что было сделано и явно спрашивать закомитать ли это.

Когда пользователь просит закоммитить:

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

Все файлы с объяснениями, проверками и планами сохранять исключительно в папке ./.kilo если пользователь прямо не указал другого!

**ВАЖНО:** Перед каждым пушем в git обновлять структуру проекта в этом файле, если были добавлены новые папки или удалены старые!

```
src/
├── bot/                      # Telegram бот
│   ├── handlers/             # Обработчики команд и сообщений
│   │   ├── payment.py        # Обработчики оплаты подписки
│   │   ├── start.py          # Обработчики start и главного меню
│   │   ├── deposit.py        # Обработчики пополнения баланса
│   │   └── admin.py          # Административные обработчики (subscriptions, payments, broadcast)
│   ├── bot.py                # Инициализация бота и диспетчера
│   ├── keyboards.py          # Клавиатуры (inline/reply)
│   ├── texts.py              # Тексты сообщений
│   └── constants.py          # Константы бота
├── infrastructure/           # Инфраструктурный слой
│   ├── database/             # Работа с БД
│   │   ├── repositories/      # Репозитории для доступа к данным
│   │   │   ├── user.py
│   │   │   ├── payment.py
│   │   │   ├── subscription.py
│   │   │   ├── encrypted_subscription.py  # VPN links из API
│   │   │   ├── referral.py
│   │   │   └── product.py    # (deprecated, будет удален)
│   │   └── session.py         # Сессии БД
│   ├── payments/              # Интеграции с платежными системами
│   │   ├── base.py            # Базовый класс платежной системы
│   │   ├── platega.py         # Интеграция с Platega
│   │   ├── factory.py         # Фабрика платежных систем
│   │   ├── schemas.py         # Pydantic схемы для платежей
│   │   └── exceptions.py      # Исключения платежных систем
│   └── vpn_subscription/      # VPN Subscription API (sub-oval.online)
│       ├── client.py          # HTTP клиент с Basic Auth
│       ├── schemas.py         # Pydantic схемы для API
│       └── exceptions.py      # Исключения VPN API
├── models/                   # SQLModel модели
│   ├── user.py               # Пользователь
│   ├── payment.py            # Платежи
│   ├── subscription.py       # Подписки (product_id nullable)
│   ├── encrypted_subscription.py  # VPN links из API
│   ├── referral.py           # Реферальные начисления
│   └── product.py            # (deprecated, будет удален)
├── services/                 # Бизнес-логика
│   ├── payment.py            # Сервис платежей
│   ├── subscription.py       # Сервис подписок (без ProductRepository)
│   ├── vpn_subscription.py   # VPN Subscription Service (API)
│   ├── tariff.py             # Сервис тарифов (DEFAULT_PRICES)
│   ├── user.py               # Сервис пользователей
│   └── referral.py           # Сервис рефералов
├── workers/                  # Background tasks
│   └── scheduler.py          # APScheduler (payment check, expiry notifications)
├── config.py                 # Конфигурация через pydantic-settings
└── main.py                   # Точка входа
tests/
├── manual/                   # Интеграционные тесты с реальными API
│   ├── test_platega_integration.py  # Тест Platega Provider
│   ├── test_payment_flow.py         # Тест полного цикла оплаты
│   └── README.md                     # Инструкции по запуску
├── infrastructure/           # Unit тесты инфраструктуры
│   └── payments/             # Тесты платежных систем
├── services/                 # Unit тесты сервисов
│   └── test_vpn_subscription.py  # Тест VPN Subscription Service
└── conftest.py               # Pytest конфигурация и fixtures
alembic/
└── versions/                 # Миграции БД
    ├── create_encrypted_subscriptions_table.py
    ├── add_subscription_type_nullable_product.py
    └── ...
```
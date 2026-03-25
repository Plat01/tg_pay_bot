# Обновленная архитектура с платежами и рефералами

## Модели базы данных

### 1. User (Пользователь)

| Поле | Тип | Описание |
|------|-----|----------|
| id | Integer (PK) | Первичный ключ |
| telegram_id | BigInteger (Unique) | ID в Telegram |
| username | String(255) - nullable | Username в Telegram |
| first_name | String(255) - nullable | Имя |
| last_name | String(255) - nullable | Фамилия |
| language_code | String(10) - nullable | Код языка |
| is_bot | Boolean | Является ли ботом |
| is_premium | Boolean | Telegram Premium |
| referral_code | String(20) (Unique) | Уникальный реферальный код |
| referred_by_id | Integer (FK -> User) - nullable | ID реферера |
| balance | Decimal(10,2) | Баланс пользователя |
| created_at | DateTime | Дата создания |
| updated_at | DateTime | Дата обновления |

### 2. Payment (Платеж)

| Поле | Тип | Описание |
|------|-----|----------|
| id | Integer (PK) | Первичный ключ |
| user_id | Integer (FK -> User) | ID плательщика |
| amount | Decimal(10,2) | Сумма платежа |
| currency | String(3) | Валюта (RUB, USD, EUR) |
| status | Enum | pending/completed/failed/cancelled |
| payment_provider | String(50) - nullable | Провайдер оплаты |
| external_id | String(255) - nullable | ID во внешней системе |
| description | String(500) - nullable | Описание платежа |
| metadata | JSON - nullable | Дополнительные данные |
| created_at | DateTime | Дата создания |
| updated_at | DateTime | Дата обновления |
| completed_at | DateTime - nullable | Дата завершения |

### 3. ReferralEarning (Реферальный заработок)

| Поле | Тип | Описание |
|------|-----|----------|
| id | Integer (PK) | Первичный ключ |
| referrer_id | Integer (FK -> User) | ID реферера (кто пригласил) |
| referral_id | Integer (FK -> User) | ID реферала (кого пригласили) |
| payment_id | Integer (FK -> Payment) | ID платежа реферала |
| amount | Decimal(10,2) | Сумма заработка |
| percent | Decimal(5,2) | Процент от платежа |
| status | Enum | pending/paid/cancelled |
| created_at | DateTime | Дата создания |
| paid_at | DateTime - nullable | Дата выплаты |

## Диаграмма связей

```mermaid
erDiagram
    User ||--o{ Payment : makes
    User ||--o{ User : refers
    User ||--o{ ReferralEarning : earns
    Payment ||--o{ ReferralEarning : generates
    User {
        int id PK
        bigint telegram_id UK
        string username
        string first_name
        string last_name
        string language_code
        bool is_bot
        bool is_premium
        string referral_code UK
        int referred_by_id FK
        decimal balance
        datetime created_at
        datetime updated_at
    }
    Payment {
        int id PK
        int user_id FK
        decimal amount
        string currency
        string status
        string payment_provider
        string external_id
        string description
        json metadata
        datetime created_at
        datetime updated_at
        datetime completed_at
    }
    ReferralEarning {
        int id PK
        int referrer_id FK
        int referral_id FK
        int payment_id FK
        decimal amount
        decimal percent
        string status
        datetime created_at
        datetime paid_at
    }
```

## Логика работы

### Регистрация с реферальным кодом

```mermaid
sequenceDiagram
    participant U as Новый пользователь
    participant B as Bot
    participant S as UserService
    participant R as UserRepository
    participant DB as PostgreSQL

    U->>B: /start ref_code_123
    B->>S: get_or_create_user - telegram_data, referral_code
    S->>R: find_by_referral_code - ref_code_123
    R->>DB: SELECT
    DB-->>R: referrer_user
    
    S->>R: get_or_create_user
    R->>DB: INSERT new user with referred_by_id
    
    Note over S: Начисляем бонус рефереру
    
    S-->>B: new_user
    B->>U: Welcome message
```

### Обработка платежа с реферальным начислением

```mermaid
sequenceDiagram
    participant U as Пользователь
    participant B as Bot
    participant PS as PaymentService
    participant RS as ReferralService
    participant DB as PostgreSQL

    U->>B: Оплата 1000 RUB
    B->>PS: create_payment - user_id, 1000, RUB
    PS->>DB: INSERT Payment - status: pending
    
    Note over U: Пользователь оплачивает
    
    PS->>DB: UPDATE Payment - status: completed
    
    alt User has referrer
        PS->>RS: process_referral_earning - payment
        RS->>DB: Get user.referrer_id
        RS->>DB: INSERT ReferralEarning
        RS->>DB: UPDATE referrer.balance
    end
    
    PS-->>B: Payment completed
    B->>U: Payment success
```

## Обновленная структура проекта

```
src/
├── models/
│   ├── __init__.py
│   ├── user.py           # User модель
│   ├── payment.py        # Payment модель
│   └── referral.py       # ReferralEarning модель
├── repositories/
│   ├── __init__.py
│   ├── base.py
│   ├── user.py
│   ├── payment.py        # PaymentRepository
│   └── referral.py       # ReferralEarningRepository
├── services/
│   ├── __init__.py
│   ├── user.py
│   ├── payment.py        # PaymentService
│   └── referral.py       # ReferralService
├── handlers/
│   ├── __init__.py
│   ├── start.py          # /start с реферальным кодом
│   └── payment.py        # Хендлеры платежей
└── ...
```

## Константы конфигурации

```python
# Реферальная система
REFERRAL_BONUS_PERCENT = Decimal("10.00")  # 10% от платежа реферала
REFERRAL_CODE_LENGTH = 8  # Длина реферального кода

# Валюты
SUPPORTED_CURRENCIES = ["RUB", "USD", "EUR"]
DEFAULT_CURRENCY = "RUB"
```

## Статусы

### PaymentStatus
- `pending` - ожидает оплаты
- `completed` - успешно оплачен
- `failed` - ошибка оплаты
- `cancelled` - отменен

### ReferralEarningStatus
- `pending` - ожидает выплаты
- `paid` - выплачен
- `cancelled` - отменен
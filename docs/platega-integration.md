# Интеграция с Platega.io

## Обзор

Platega.io - платежная система для приема платежей в криптовалюте и фиатных валютах. Документация API: https://docs.platega.io/

## Архитектура

Интеграция реализована в слое инфраструктуры (`src/infrastructure/payments/`):

```
src/infrastructure/payments/
├── __init__.py      # Экспорты модуля
├── base.py          # Абстрактный класс PaymentProvider
├── platega.py       # Реализация для Platega API
├── factory.py       # Фабрика провайдеров
├── schemas.py       # Pydantic модели для API
├── exceptions.py    # Кастомные исключения
└── retry.py         # Retry логика с exponential backoff
```

### Почему infrastructure/payments?

Папка `src/infrastructure/` содержит адаптеры для внешних сервисов. Это отдельный слой от бизнес-логики:

| Слой | Назначение | Примеры |
|------|------------|---------|
| `src/models/` | Модели данных (БД) | Payment, User |
| `src/repositories/` | Доступ к данным | PaymentRepository |
| `src/services/` | Бизнес-логика | PaymentService |
| `src/infrastructure/` | Внешние интеграции | PlategaProvider |

## Компоненты

### PaymentProvider (ABC)

Абстрактный интерфейс для платежных провайдеров:

```python
class PaymentProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...
    
    @abstractmethod
    async def create_payment(
        self,
        amount: Decimal,
        currency: str,
        description: str,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> CreatePaymentResult: ...
    
    @abstractmethod
    async def get_payment_status(
        self,
        external_id: str,
    ) -> PaymentStatusResult: ...
    
    @abstractmethod
    def map_status(self, external_status: str) -> PaymentStatus: ...
    
    @abstractmethod
    async def close(self) -> None: ...
```

### PlategaProvider

HTTP клиент для Platega API:

- **create_payment()** - создание транзакции через `POST /transaction/process`
- **get_payment_status()** - проверка статуса через `GET /transaction/{id}`
- **parse_webhook()** - парсинг webhook с проверкой HMAC-SHA256 подписи
- **map_status()** - маппинг статусов Platega → PaymentStatus

### PaymentProviderFactory

Фабрика для создания провайдеров:

```python
# Создать провайдера по имени
provider = PaymentProviderFactory.create("platega")

# Получить провайдера по умолчанию из настроек
provider = PaymentProviderFactory.get_default()
```

### Pydantic схемы

Модели для валидации запросов и ответов:

- `PlategaCreateRequest` - запрос на создание транзакции
- `PlategaCreateResponse` - ответ с URL для оплаты
- `PlategaStatusResponse` - ответ со статусом транзакции
- `PlategaPaymentMethod` - enum методов оплаты

### Исключения

- `PaymentProviderError` - базовое исключение
- `PaymentCreationError` - ошибка создания платежа
- `PaymentStatusError` - ошибка получения статуса
- `PaymentProviderUnavailable` - провайдер недоступен
- `PaymentValidationError` - ошибка валидации данных
- `PaymentSignatureError` - ошибка проверки подписи webhook
- `PaymentTimeoutError` - таймаут запроса

## Методы оплаты

Platega поддерживает следующие методы:

| Метод | Описание |
|-------|----------|
| `SBP_QR` (2) | СБП QR-код |
| `ERIP` (3) | ЕРИП (Беларусь) |
| `CARD_ACQUIRING` (11) | Банковская карта (РФ) |
| `INTERNATIONAL` (12) | Международная карта |
| `CRYPTO` (13) | Криптовалюта |

## Конфигурация

### Переменные окружения

```env
# Platega API
PLATEGA_API_KEY=your_api_key
PLATEGA_SHOP_ID=your_shop_id
PLATEGA_WEBHOOK_SECRET=your_webhook_secret
PLATEGA_API_URL=https://api.platega.io
PLATEGA_WEBHOOK_URL=https://your-domain.com/webhook/platega
DEFAULT_PAYMENT_PROVIDER=platega
```

### Settings

Настройки в `src/config.py`:

```python
class Settings(BaseSettings):
    # Platega Payment Provider
    platega_api_key: str = ""
    platega_shop_id: str = ""
    platega_webhook_secret: str = ""
    platega_api_url: str = "https://api.platega.io"
    platega_webhook_url: str = ""
    default_payment_provider: str = "platega"
```

## Использование

### Создание платежа

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

if result.success:
    print(f"Payment URL: {result.payment_url}")
    print(f"External ID: {result.external_id}")
else:
    print(f"Error: {result.error_message}")
```

### Проверка статуса

```python
status_result = await provider.get_payment_status("transaction_uuid")
print(f"Status: {status_result.status}")
```

### Обработка webhook

```python
from aiohttp import web

async def webhook_handler(request: web.Request) -> web.Response:
    raw_body = await request.read()
    headers = dict(request.headers)
    
    try:
        webhook_data = provider.parse_webhook(raw_body, headers)
        print(f"Payment {webhook_data.payment_id}: {webhook_data.status}")
        return web.Response(status=200, text="OK")
    except PaymentSignatureError:
        return web.Response(status=401, text="Invalid signature")
```

## Маппинг статусов

| Platega | Internal |
|---------|----------|
| PENDING | PENDING |
| CONFIRMED | COMPLETED |
| CANCELED | CANCELLED |
| CHARGEBACKED | FAILED |

## Retry логика

Провайдер автоматически повторяет запросы при ошибках:

- Максимум попыток: 3
- Базовая задержка: 1 секунда
- Экспоненциальный рост: 2x
- Максимальная задержка: 30 секунд
- Таймаут запроса: 10 секунд

## Безопасность

1. **Webhook подпись** - проверка HMAC-SHA256
2. **API Key** - авторизация через Bearer token
3. **Timeout** - защита от зависших запросов

## Добавление нового провайдера

1. Создать класс, наследующий `PaymentProvider`:

```python
# src/infrastructure/payments/yookassa.py
class YooKassaProvider(PaymentProvider):
    @property
    def name(self) -> str:
        return "yookassa"
    
    # ... реализация методов
```

2. Зарегистрировать в фабрике:

```python
# src/infrastructure/payments/factory.py
_providers: dict[str, type[PaymentProvider]] = {
    "platega": PlategaProvider,
    "yookassa": YooKassaProvider,
}
```

3. Добавить конфигурацию в `src/config.py`

## Тестирование

```bash
# Запуск тестов
pytest tests/infrastructure/payments/
```

## Ссылки

- [Platega API Documentation](https://docs.platega.io/)
- [Platega Dashboard](https://dashboard.platega.io/)
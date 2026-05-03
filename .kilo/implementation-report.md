# Отчет о реализации интеграции с sub-oval.online

## Выполненные изменения

### 1. VPN Subscription API Client

**Созданы файлы:**
- `src/infrastructure/vpn_subscription/__init__.py`
- `src/infrastructure/vpn_subscription/client.py` - HTTP клиент с Basic Auth
- `src/infrastructure/vpn_subscription/schemas.py` - Pydantic схемы для API
- `src/infrastructure/vpn_subscription/exceptions.py` - Исключения VPN API

**Методы клиента:**
- `create_encrypted_subscription()` - POST `/api/v1/admin/subscriptions/encrypted`
- `get_subscription_config()` - GET `/api/v1/subscriptions/{public_id}`
- `list_vpn_sources()` - GET `/api/v1/admin/vpn-sources`
- `health_check()` - GET `/api/v1/health`

### 2. EncryptedSubscription Model

**Созданы файлы:**
- `src/models/encrypted_subscription.py` - Model для хранения VPN links
- `src/infrastructure/database/repositories/encrypted_subscription.py` - Repository

**Поля модели:**
- `id` - UUID из API
- `subscription_id` - FK к subscriptions (nullable для trial)
- `public_id` - для получения config
- `encrypted_link` - ссылка для пользователя
- `vpn_sources_count`, `tags_used`, `expires_at`, `ttl_hours`, `max_devices`

### 3. VPN Subscription Service

**Создан файл:**
- `src/services/vpn_subscription.py`

**Методы сервиса:**
- `create_subscription_for_tariff()` - создает encrypted subscription через API
- `get_or_create_for_subscription()` - ленивая миграция
- `create_trial_subscription()` - trial (72 hours TTL)
- `refresh_subscription_link()` - обновление link

**Metadata из .env:**
- `profile_title` = BOT_NAME
- `support_url` = SUPPORT_LINK
- `profile_web_page_url` = BOT_LINK
- `announce` = "Проверяйте пинг перед подключением"
- `info_block` = configurable

### 4. Рефакторинг Services

**Обновлены файлы:**
- `src/services/subscription.py` - удален ProductRepository, добавлен subscription_type
- `src/services/payment.py` - удален ProductRepository, используется VPN Subscription Service
- `src/services/tariff.py` - удален ProductRepository, цены из DEFAULT_PRICES

**Изменения:**
- Subscription.product_id теперь nullable
- Subscription.subscription_type - новый field для типа подписки
- VPN link создается через API при покупке

### 5. Рефакторинг Handlers

**Обновлены файлы:**
- `src/bot/handlers/admin.py` - удален `/send_sub_links` и связанные handlers
- `src/bot/handlers/start.py` - trial и get_subscription_link используют VPN API
- `src/bot/handlers/payment.py` - balance payment использует VPN API
- `src/bot/constants.py` - удален SEND_SUBSCRIPTION_LINKS

### 6. Миграции БД

**Созданы файлы:**
- `alembic/versions/create_encrypted_subscriptions_table.py`
- `alembic/versions/add_subscription_type_nullable_product.py`

**Изменения схемы:**
- Создана таблица `encrypted_subscriptions`
- `subscriptions.product_id` - nullable
- `subscriptions.subscription_type` - новый column

### 7. Конфигурация

**Обновлен `src/config.py`:**
- `vpn_sub_api_url` - URL API
- `vpn_sub_admin_username` - Basic Auth username
- `vpn_sub_admin_password` - Basic Auth password
- `default_max_devices` = 3
- `default_announce_text`, `default_info_block_text`, `default_info_block_color`

### 8. Документация

**Обновлен `docs/admin-guide.md`:**
- Удалена секция `/send_sub_links`
- Добавлена секция про VPN Subscription API
- Обновлены troubleshooting секции
- Обновлены сценарии использования
- Добавлена секция 9.6 VPN Subscription API параметры

**Обновлен `AGENTS.md`:**
- Добавлена структура vpn_subscription/
- Добавлена структура encrypted_subscription model
- Обновлена структура services

### 9. Тесты

**Созданы файлы:**
- `tests/services/__init__.py`
- `tests/services/test_vpn_subscription.py`

---

## Что осталось удалить (deprecated)

### Product-related files (в будущем):
- `src/models/product.py`
- `src/infrastructure/database/repositories/product.py`
- Миграция для удаления таблицы `products`

### Временные решения:
- ProductRepository остается импортированным в некоторых файлах (но не используется)
- Product model импортируется в models/__init__.py (для совместимости с существующими данными)

---

## Ленивая миграция VPN links

Существующие VPN links мигрируются при первом запросе пользователя:
1. Пользователь нажимает 🔗 monthly/yearly в профиле
2. Если нет encrypted_subscription - создается через API
3. Link сохраняется в БД

---

## TTL Hours Mapping

```
trial:    72 hours (3 days)
monthly:  720 hours (30 days)
quarterly: 2160 hours (90 days)
yearly:   8760 hours (365 days)
```

---

## VpnTag Enum

```python
class VpnTag(str, Enum):
    MAIN = "main"
    # Расширяемый в будущем
```

---

## Для запуска

1. Добавить в `.env`:
```
VPN_SUB_API_URL=https://sub-oval.online
VPN_SUB_ADMIN_USERNAME=admin
VPN_SUB_ADMIN_PASSWORD=sdfgkuhb87vs
```

2. Применить миграции:
```
alembic upgrade head
```

3. Проверить health API:
```
GET https://sub-oval.online/api/v1/health
```
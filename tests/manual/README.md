# Manual/Integration Tests

Интеграционные тесты для проверки реального прохождения платежей через Platega API.

## Предварительные требования

1. **Настроенный .env файл** с реальными ключами Platega:
   ```bash
   PLATEGA_MERCHANT_ID=your_real_merchant_id
   PLATEGA_SECRET=your_real_api_secret
   PLATEGA_API_URL=https://app.platega.io
   ```

2. **Запущенная база данных** (для тестов с PaymentService):
   ```bash
   docker-compose up -d db
   ```

3. **Пользователь в базе** с telegram_id = "123456789" (или измените в тесте)

## Запуск тестов

### 1. Простой тест Platega Provider

Тестирует напрямую PlategaProvider без базы данных:

```bash
# Через pytest
python -m pytest tests/manual/test_platega_integration.py -v -s

# Или напрямую
python tests/manual/test_platega_integration.py
```

**Что проверяет:**
- Создание платежа для разных методов (SBP_QR, CARD_ACQUIRING, INTERNATIONAL)
- Получение статуса платежа
- Парсинг webhook
- Логирование всех HTTP запросов/ответов

### 2. Полный тест PaymentService

Тестирует PaymentService с базой данных:

```bash
python tests/manual/test_payment_flow.py
```

**Что проверяет:**
- Создание платежа через PaymentService
- Запись в базу данных
- Проверка статуса через provider
- Получение платежа по external_id
- Получение платежей пользователя
- Обработка метода CARD_ACQUIRING (с ошибкой "No available card cascades")

## Что ожидать

### Успешный сценарий (SBP_QR)

```
✅ ПЛАТЕЖ УСПЕШНО СОЗДАН!
   Transaction ID: uuid-here
   Payment URL: https://pay.platega.io/...
   
ИНФОРМАЦИЯ ДЛЯ ОПЛАТЫ
Payment URL: https://pay.platega.io/...
QR Code: https://qr.example.com/...
```

### Ошибка с CARD_ACQUIRING

```
⚠️  ПЛАТЕЖ НЕ СОЗДАН
   Причина: No available card cascades
   Но transactionId присутствует: uuid-here
   
Это исправленная проблема!
```

## Логирование

Все тесты используют `logging.DEBUG` уровень, поэтому вы увидите:
- Полные HTTP запросы
- Полные HTTP ответы от Platega
- Все шаги PaymentService
- SQL запросы к базе (если настроен SQLAlchemy logging)

## Отладка проблемы "No available card cascades"

После исправления кода, при запуске test_card_acquiring_method():
- Если Platega вернет HTTP 400 с transactionId → external_id будет сохранен
- Если Platega вернет HTTP 400 без transactionId → ValueError "пустой external_id"

Проверьте логи:
```
Platega API response: {'status': 400, 'response_data': {...}}
```

Если в response_data есть transactionId → проблема решена!

## Дополнительные тесты

Для тестирования webhook handlers бота, нужно:
1. Запустить бота: `python src/main.py`
2. Создать платеж через бота в Telegram
3. Отправить webhook от Platega на ваш сервер
4. Проверить обработку webhook в логах бота

## Примечания

- Тесты используют реальные деньги (малые суммы: 299 ₽)
- Платежи создаются в статусе PENDING
- Для завершения нужно реально оплатить по URL/QR
- После оплаты статус изменится на CONFIRMED через webhook или check_and_update_status
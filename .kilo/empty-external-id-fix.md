# Fix: Пустой external_id в платежах

## Проблема

**Error:**
```
ValueError: Payment f68f4344-7697-4b04-b92d-11e810062957 has no external_id, cannot check status with provider
```

**Root Cause:**
- `CreatePaymentResult.external_id` имеет default value `""` (empty string)
- Если Platega API fails → возвращает `external_id = ""`
- Payment сохраняется в DB с пустым external_id
- Repository filter `.where(Payment.external_id.isnot(None))` исключает **None**, но НЕ `""`
- Scheduler пытается проверить платеж → ValueError

**Почему происходило:**
```python
# Provider returned:
external_result.external_id = ""  # Empty string

# Saved to DB:
payment.external_id = ""  # Not None!

# Repository filter:
.where(Payment.external_id.isnot(None))  # "" passes through!

# Scheduler tries:
await provider.get_payment_status("")  # ❌ Invalid ID
```

## Решение

### 1. PaymentService - Валидация перед сохранением

**File: `src/services/payment.py` (строка 235)**

```python
# После создания платежа в provider:
external_result = await self.provider.create_payment(...)

# Validate external_id before saving
if not external_result.external_id or external_result.external_id.strip() == "":
    logger.error(
        f"Provider returned empty external_id",
        extra={
            "telegram_id": telegram_id,
            "amount": str(amount),
            "provider": self.provider_name,
            "success": external_result.success,
            "error_message": external_result.error_message,
        },
    )
    raise ValueError(
        "Платеж не создан: провайдер вернул пустый external_id. "
        "Попробуйте еще раз или выберите другой способ оплаты."
    )

# Save to database only if external_id is valid
payment = await self.create_payment(...)
```

### 2. Payment Handler - Понятное сообщение пользователю

**File: `src/bot/handlers/payment.py` (строка 160)**

```python
except ValueError as e:
    # Specific error for empty external_id or validation errors
    logger.error(
        f"Payment validation error: {e}",
        extra={...},
    )

    await callback.message.edit_text(
        f"❌ <b>Ошибка создания платежа</b>\n\n"
        f"{str(e)}",  # Show actual error message
        parse_mode="HTML",
        reply_markup=Keyboards.error_with_support_link(),
    )

except Exception as e:
    # Generic error handler
    await callback.message.edit_text(
        "❌ <b>Ошибка создания платежа</b>\n\n"
        "Не удалось создать платеж. Попробуйте еще раз или обратитесь в поддержку.",
        parse_mode="HTML",
        reply_markup=Keyboards.error_with_support_link(),
    )
```

### 3. Repository - Фильтрация пустых строк

**File: `src/infrastructure/database/repositories/payment.py`**

```python
# In both methods: get_active_pending_payments() and get_expired_pending_payments()

statement = (
    select(Payment)
    .where(Payment.status == PaymentStatus.PENDING)
    .where(Payment.created_at > newer_than)
    .where(Payment.external_id.isnot(None))  # Exclude None
    .where(Payment.external_id != "")  # ✅ NEW: Exclude empty strings
    .order_by(Payment.created_at.asc())
    .limit(limit)
)
```

## User Experience

**До фикса:**
1. User создает платеж
2. Provider fails → returns empty external_id
3. Payment saved to DB (silent failure)
4. User не видит ошибку → думает платеж создан
5. Scheduler пытается проверить → crash
6. User не получает продукт

**После фикса:**
1. User создает платеж
2. Provider fails → returns empty external_id
3. **Validation catches empty external_id**
4. **User sees:** "❌ Платеж не создан: провайдер вернул пустый external_id. Попробуйте еще раз или выберите другой способ оплаты."
5. Payment NOT saved to DB
6. User can retry or contact support
7. No scheduler errors

## Benefits

1. **Early validation:** Ошибка ловится сразу при создании, не позже
2. **User-friendly message:** Понятное сообщение что делать
3. **No silent failures:** Платеж не создается с пустым external_id
4. **Scheduler safety:** Scheduler не пытается проверить invalid платежи
5. **Better debugging:** Logs show provider error details

## Testing

**Test case 1: Provider returns empty external_id**
```python
# Mock provider response:
external_result.external_id = ""
external_result.error_message = "API timeout"

# Expected:
- Payment NOT saved to DB
- User sees: "Платеж не создан, попробуйте еще раз"
- Log: "Provider returned empty external_id"
```

**Test case 2: Existing payments with empty external_id**
```python
# Payment in DB:
external_id = ""

# Expected:
- Repository filter excludes it
- Scheduler doesn't try to check
- No ValueError in logs
```

## Files Changed

1. `src/services/payment.py` - Added validation
2. `src/bot/handlers/payment.py` - Better error handling
3. `src/infrastructure/database/repositories/payment.py` - Filter empty strings

## Commit

```
fix: предотвращение создания платежей с пустым external_id

- Добавлена проверка external_id в PaymentService.create_external_payment()
- Если external_id пустой → ValueError с понятным сообщением
- Пользователь видит: 'Платеж не создан, попробуйте еще раз'
- Repository фильтрует пустые строки в обоих методах
- Scheduler не будет пытаться проверить платежи без external_id
```

## Additional Notes

- Также добавлен `.where(Payment.external_id != "")` в оба repository метода
- Это гарантирует что даже если пустой платеж somehow попал в DB, scheduler его не проверит
- Двойная защита: validation при создании + фильтрация при выборке

## Future Improvements

1. Add retry logic with different payment method
2. Add fallback provider (if Platega fails, try another)
3. Add monitoring/alerting for provider failures
4. Add user notification about provider status
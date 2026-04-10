# Plan: Automatic PENDING Payment Checker

## Problem Statement

**Current Issue:** Payments in PENDING status stay forever if user doesn't click "Я оплатил" button. Need to:
1. Automatically check PENDING payments older than 1 hour
2. Transition to EXPIRED if not completed
3. Deliver product if payment succeeded (subscription OR balance top-up)
4. Send Telegram notification to user on auto-completion
5. Log failures appropriately

## User Preferences (Confirmed)

- ✅ **Check interval:** Every 5 minutes
- ✅ **Notifications:** Send Telegram message with payment details and delivered product
- ✅ **Worker type:** APScheduler (robust, extensible)
- ✅ **Balance deposits:** Account for future implementation, focus on subscriptions now

## Architecture Analysis

### Current Payment Types

**Two payment flows exist:**

1. **Subscription Payment** (`src/bot/handlers/payment.py`)
   - Description: `"Подписка: {tariff_label}"`
   - Success action: Create subscription + send VPN link
   - Currently in: `handle_confirm_payment()` lines 230-275

2. **Balance Deposit** (`src/bot/handlers/deposit.py`)
   - Description: `"Пополнение баланса"`
   - Success action: Increase user.balance
   - Currently in: Not implemented! Deposit handler only checks status, doesn't auto-complete

### Key Finding

**Balance deposits don't auto-complete!** The `deposit.py` handler only:
- Creates payment
- Checks status manually
- But NEVER updates user balance on success

This is a **missing feature** - balance deposits only work if manually verified.

## Solution Architecture

### Components Needed

1. **Background Worker** - Periodic task to check stale PENDING payments
2. **Payment Completer Service** - Logic to deliver product on success
3. **Repository Method** - Find PENDING payments older than expiry timeout
4. **Configuration** - Timeout values, check interval

### Design Decisions

**How to differentiate payment types:**
```python
if payment.description and payment.description.startswith("Подписка:"):
    # Subscription payment - create subscription
elif payment.description and payment.description.startswith("Пополнение"):
    # Balance deposit - update user.balance
```

**Where to deliver product logic:**
- Extract from `handle_confirm_payment()` into `PaymentService.complete_payment_and_deliver()`
- Reuse in both manual (button click) and automatic (background worker) flows

## Implementation Plan

### Phase 1: Extract Product Delivery Logic

**File: src/services/payment.py**

Add new method:
```python
async def complete_payment_and_deliver(
    self,
    payment: Payment,
    telegram_id: str,
) -> dict:
    """Complete payment and deliver appropriate product.
    
    Handles both subscription and balance deposit payments.
    
    Args:
        payment: Payment to complete
        telegram_id: User Telegram ID for notifications
        
    Returns:
        Dict with delivery details (subscription_id, vpn_link, etc.)
        
    Raises:
        ValueError: If payment type unknown or product not found
    """
    # Determine payment type by description
    if payment.description.startswith("Подписка:"):
        return await self._deliver_subscription(payment)
    elif payment.description.startswith("Пополнение"):
        return await self._deliver_balance_topup(payment)
    else:
        raise ValueError(f"Unknown payment type: {payment.description}")
```

Add helper methods:
```python
async def _deliver_subscription(self, payment: Payment) -> dict:
    """Create subscription for successful payment."""
    # Extract tariff from price
    tariff_type = get_tariff_by_price(int(payment.amount))
    if not tariff_type:
        raise ValueError(f"Cannot determine tariff for amount {payment.amount}")
    
    # Get product
    product = await self.product_repository.get_product_by_subscription_type(tariff_type)
    if not product:
        raise ValueError(f"Product not found for tariff {tariff_type}")
    
    # Create subscription
    subscription = await self.subscription_service.create_subscription(
        user_id=payment.user_id,
        product_id=product.id,
        duration_days=product.duration_days,
    )
    
    return {
        "type": "subscription",
        "subscription_id": subscription.id,
        "vpn_link": product.happ_link,
        "duration_days": product.duration_days,
    }

async def _deliver_balance_topup(self, payment: Payment) -> dict:
    """Update user balance for successful deposit."""
    # Get user
    user = await self.user_repository.get_by_id(payment.user_id)
    if not user:
        raise ValueError(f"User not found: {payment.user_id}")
    
    # Update balance
    new_balance = user.balance + payment.amount
    user = await self.user_repository.update(user, {"balance": new_balance})
    
    return {
        "type": "balance",
        "amount": payment.amount,
        "new_balance": user.balance,
    }
```

**File: src/bot/handlers/payment.py**

Replace lines 230-275 with:
```python
if payment.status == PaymentStatus.COMPLETED:
    try:
        delivery_result = await payment_service.complete_payment_and_deliver(
            payment, str(callback.from_user.id)
        )
        
        if delivery_result["type"] == "subscription":
            await callback.message.edit_text(
                Texts.PAYMENT_SUCCESS_RESULT.format(
                    duration=delivery_result["duration_days"],
                    vpn_link=delivery_result["vpn_link"],
                ),
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_menu(),
            )
    except ValueError as e:
        logger.error(f"Failed to deliver product: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка выдачи товара: {str(e)}",
            parse_mode="HTML",
            reply_markup=Keyboards.back_to_menu(),
        )
```

**File: src/bot/handlers/deposit.py**

Add auto-completion logic (currently missing!):
```python
if payment.status == PaymentStatus.COMPLETED:
    try:
        delivery_result = await payment_service.complete_payment_and_deliver(
            payment, str(callback.from_user.id)
        )
        
        if delivery_result["type"] == "balance":
            await callback.message.edit_text(
                Texts.DEPOSIT_SUCCESS.format(
                    amount=delivery_result["amount"],
                    balance=delivery_result["new_balance"],
                ),
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_menu(),
            )
    except ValueError as e:
        logger.error(f"Failed to process deposit: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка обработки пополнения: {str(e)}",
            parse_mode="HTML",
            reply_markup=Keyboards.back_to_menu(),
        )
```

### Phase 2: Add Repository Method

**File: src/infrastructure/database/repositories/payment.py**

Add method:
```python
async def get_stale_pending_payments(
    self,
    older_than: datetime,
    limit: int = 100,
) -> list[Payment]:
    """Get PENDING payments older than specified datetime.
    
    Args:
        older_than: Datetime threshold (payments created before this)
        limit: Maximum number of payments to return
        
    Returns:
        List of PENDING Payment instances.
    """
    statement = (
        select(Payment)
        .where(Payment.status == PaymentStatus.PENDING)
        .where(Payment.created_at < older_than)
        .where(Payment.external_id.isnot(None))  # Only payments with external ID
        .order_by(Payment.created_at.asc())
        .limit(limit)
    )
    result = await self.session.execute(statement)
    return list(result.scalars().all())
```

### Phase 3: Background Worker with APScheduler

**File: pyproject.toml**

Add dependency:
```toml
dependencies = [
    # ... existing deps
    "apscheduler>=3.10.0",
]
```

**File: src/workers/scheduler.py (NEW)**

```python
"""Background scheduler for periodic tasks."""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.config import settings
from src.infrastructure.database import async_session_maker
from src.bot.bot import bot
from src.models.payment import PaymentStatus
from src.services.payment import PaymentService
from src.bot.texts import Texts

logger = logging.getLogger(__name__)


scheduler = AsyncIOScheduler()


async def check_pending_payments_job() -> None:
    """Job to check stale PENDING payments.
    
    Called by APScheduler every PAYMENT_CHECK_INTERVAL_MINUTES.
    """
    expiry_timeout_hours = getattr(settings, 'payment_expiry_timeout_hours', 1)
    older_than = datetime.now(timezone.utc) - timedelta(hours=expiry_timeout_hours)
    
    logger.info(
        f"Checking stale PENDING payments",
        extra={
            "older_than": older_than.isoformat(),
            "expiry_timeout_hours": expiry_timeout_hours,
        },
    )
    
    async with async_session_maker() as session:
        payment_service = PaymentService(session)
        
        # Get stale payments
        stale_payments = await payment_service.repository.get_stale_pending_payments(
            older_than=older_than,
            limit=100,
        )
        
        if not stale_payments:
            logger.debug("No stale PENDING payments found")
            return
        
        logger.info(
            f"Found {len(stale_payments)} stale PENDING payments",
            extra={"count": len(stale_payments)},
        )
        
        # Process each payment
        for payment in stale_payments:
            try:
                await process_stale_payment(payment_service, payment)
            except Exception as e:
                logger.error(
                    f"Failed to process payment {payment.id}: {e}",
                    extra={
                        "payment_id": str(payment.id),
                        "user_id": str(payment.user_id),
                    },
                    exc_info=True,
                )


async def process_stale_payment(
    payment_service: PaymentService,
    payment: Payment,
) -> None:
    """Process one stale PENDING payment.
    
    Args:
        payment_service: PaymentService instance
        payment: Payment to process
    """
    logger.info(
        f"Processing stale payment",
        extra={
            "payment_id": str(payment.id),
            "external_id": payment.external_id,
            "amount": str(payment.amount),
            "created_at": payment.created_at.isoformat(),
        },
    )
    
    # Check status with provider
    payment = await payment_service.check_and_update_status(payment)
    
    # Handle result
    if payment.status == PaymentStatus.COMPLETED:
        # Payment succeeded - deliver product and notify user
        logger.info(
            f"Stale payment completed successfully",
            extra={
                "payment_id": str(payment.id),
                "status": payment.status.value,
            },
        )
        
        try:
            # Get user for telegram_id
            user = await payment_service.user_repository.get_by_id(payment.user_id)
            if user:
                # Deliver product
                delivery_result = await payment_service.complete_payment_and_deliver(
                    payment, user.telegram_id
                )
                
                logger.info(
                    f"Product delivered for stale payment",
                    extra={
                        "payment_id": str(payment.id),
                        "delivery_type": delivery_result.get("type"),
                    },
                )
                
                # Send notification to user
                await notify_user_payment_completed(
                    telegram_id=user.telegram_id,
                    amount=payment.amount,
                    delivery_result=delivery_result,
                )
        except Exception as e:
            logger.error(
                f"Failed to deliver product or notify user: {e}",
                extra={"payment_id": str(payment.id)},
                exc_info=True,
            )
    
    elif payment.status == PaymentStatus.FAILED:
        logger.warning(
            f"Stale payment failed",
            extra={
                "payment_id": str(payment.id),
                "status": payment.status.value,
            },
        )
    
    elif payment.status == PaymentStatus.CANCELLED:
        logger.warning(
            f"Stale payment cancelled",
            extra={
                "payment_id": str(payment.id),
                "status": payment.status.value,
            },
        )
    
    elif payment.status == PaymentStatus.PENDING:
        # Still pending after check - mark as EXPIRED
        logger.warning(
            f"Stale payment still pending, marking as expired",
            extra={
                "payment_id": str(payment.id),
                "created_at": payment.created_at.isoformat(),
            },
        )
        
        payment = await payment_service.repository.update_status(
            payment,
            PaymentStatus.EXPIRED,
        )
        
        logger.info(
            f"Payment marked as expired",
            extra={
                "payment_id": str(payment.id),
                "status": payment.status.value,
            },
        )


async def notify_user_payment_completed(
    telegram_id: str,
    amount: str,
    delivery_result: dict,
) -> None:
    """Send Telegram notification to user about auto-completed payment.
    
    Args:
        telegram_id: User Telegram ID
        amount: Payment amount
        delivery_result: Dict with delivery details
    """
    try:
        # Send payment confirmation
        await bot.send_message(
            telegram_id,
            Texts.PAYMENT_AUTO_COMPLETED.format(amount=amount),
            parse_mode="HTML",
        )
        
        # Send product delivery message based on type
        if delivery_result.get("type") == "subscription":
            await bot.send_message(
                telegram_id,
                Texts.PAYMENT_SUCCESS_RESULT.format(
                    duration=delivery_result["duration_days"],
                    vpn_link=delivery_result["vpn_link"],
                ),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        elif delivery_result.get("type") == "balance":
            await bot.send_message(
                telegram_id,
                Texts.DEPOSIT_SUCCESS.format(
                    amount=delivery_result["amount"],
                    balance=delivery_result["new_balance"],
                ),
                parse_mode="HTML",
            )
        
        logger.info(
            f"User notified about auto-completed payment",
            extra={
                "telegram_id": telegram_id,
                "amount": amount,
                "delivery_type": delivery_result.get("type"),
            },
        )
    except Exception as e:
        logger.error(
            f"Failed to notify user: {e}",
            extra={"telegram_id": telegram_id},
            exc_info=True,
        )


def setup_scheduler() -> None:
    """Setup APScheduler with payment checker job."""
    check_interval_minutes = getattr(settings, 'payment_check_interval_minutes', 5)
    
    logger.info(
        f"Setting up scheduler",
        extra={"check_interval_minutes": check_interval_minutes},
    )
    
    # Add payment checker job
    scheduler.add_job(
        check_pending_payments_job,
        trigger=IntervalTrigger(minutes=check_interval_minutes),
        id="payment_checker",
        name="Check stale PENDING payments",
        max_instances=1,  # Prevent overlapping runs
        replace_existing=True,
    )
    
    logger.info(f"Payment checker job scheduled every {check_interval_minutes} minutes")


def start_scheduler() -> None:
    """Start the scheduler."""
    if not scheduler.running:
        setup_scheduler()
        scheduler.start()
        logger.info("Scheduler started")
    else:
        logger.warning("Scheduler already running")


def shutdown_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler shutdown complete")
```

**Recommendation: APScheduler** as requested by user - more robust, supports multiple scheduled tasks, persistent jobs.

### Phase 4: Integration with APScheduler

**File: src/main.py**

Start scheduler:
```python
from src.workers.scheduler import start_scheduler, shutdown_scheduler

async def main() -> None:
    """Start the bot."""
    logger.info("Starting bot...")
    
    # Start scheduler for background tasks
    start_scheduler()
    logger.info("Scheduler started")
    
    # Notify admins about restart
    await notify_admins()
    
    # Start polling
    try:
        await dp.start_polling(bot, parse_mode=ParseMode.HTML)
    finally:
        # Shutdown scheduler gracefully
        shutdown_scheduler()
        await bot.session.close()
```

### Phase 5: Configuration

**File: src/config.py**

Add settings:
```python
# Payment Auto-Check
payment_check_interval_minutes: int = 5  # Check every 5 minutes
payment_expiry_timeout_hours: int = 1  # Mark as expired after 1 hour
```

**File: .env.example**

Add:
```env
# Payment auto-check settings
PAYMENT_CHECK_INTERVAL_MINUTES=5
PAYMENT_EXPIRY_TIMEOUT_HOURS=1
```

### Phase 6: Add Missing Texts

**File: src/bot/texts.py**

Add auto-completion notification:
```python
PAYMENT_AUTO_COMPLETED = (
    "✅ <b>Платеж автоматически обработан!</b>\n\n"
    "💰 Сумма: {amount} ₽\n"
    "✅ Статус: Успешно завершен"
)
```

Add deposit success message (for future balance deposits):
```python
DEPOSIT_SUCCESS = (
    "✅ <b>Баланс успешно пополнен!</b>\n\n"
    "💰 Пополнено: {amount} ₽\n"
    "💳 Новый баланс: {balance} ₽"
)
```

## Edge Cases & Considerations

### 1. Race Conditions

**Problem:** User clicks "Я оплатил" while background worker also checking same payment.

**Solution:** Database transaction isolation + check current status before updating:
```python
# In process_stale_payment
payment = await payment_service.check_and_update_status(payment)
# check_and_update_status already checks current status first
```

### 2. Subscription Already Exists

**Problem:** Payment completed manually by user click, then background worker tries to create subscription again.

**Solution:** Check if user already has active subscription:
```python
# In _deliver_subscription
existing_sub = await self.subscription_service.get_active_subscription(payment.user_id)
if existing_sub:
    logger.warning(f"User already has subscription, skipping")
    return {...}
```

### 3. Missing Products

**Problem:** Tariff price doesn't match any product.

**Solution:** Already handled with ValueError, logged appropriately.

### 4. Provider API Limits

**Problem:** Checking too many payments at once may hit Platega rate limits.

**Solution:** 
- Limit batch size (100 payments)
- Process sequentially, not in parallel
- Add rate limiting if needed

### 5. Database Connection

**Problem:** Long-running worker may accumulate database connections.

**Solution:** Use fresh session for each batch:
```python
async with async_session_maker() as session:
    # Process batch
    # Session automatically closed after block
```

## Testing Strategy

### Unit Tests

**File: tests/services/test_payment_delivery.py (NEW)**

Test product delivery logic:
- `_deliver_subscription()` creates subscription correctly
- `_deliver_balance_topup()` updates balance correctly
- `complete_payment_and_deliver()` handles both types

### Integration Tests

**File: tests/workers/test_payment_checker.py (NEW)**

Test background worker:
- Finds stale payments correctly
- Transitions to EXPIRED correctly
- Delivers product on success

### Manual Testing

1. Create payment, don't pay
2. Wait > 1 hour
3. Verify payment marked as EXPIRED
4. Create payment, pay via SBP
5. Don't click "Я оплатил"
6. Wait for background check
7. Verify subscription created automatically

## File Structure

```
src/
├── workers/                    # NEW: Background workers
│   └ scheduler.py              # NEW: APScheduler setup + payment checker job
├── services/
│   ├── payment.py              # MODIFY: Add delivery methods + dependencies
│   └── subscription.py         # Existing (no changes)
│   └ user.py                   # Existing (no changes)
│   └ bot/subscription_prices.py # Import for tariff detection
├── infrastructure/database/repositories/
│   └ payment.py                # MODIFY: Add get_stale_pending_payments
├── bot/
│   ├── handlers/
│   │   ├── payment.py          # MODIFY: Use delivery service method
│   │   └ deposit.py            # MODIFY: Add delivery on success (future)
│   └ texts.py                  # MODIFY: Add auto-completion notification
│   └ bot.py                    # Existing (imported for notifications)
├── config.py                   # MODIFY: Add check settings
└── main.py                     # MODIFY: Start scheduler
pyproject.toml                  # MODIFY: Add APScheduler dependency
```

## Estimated Implementation Time

- Add APScheduler dependency: 2 minutes
- Phase 1 (Extract delivery logic): 15 minutes
- Phase 2 (Repository method): 5 minutes
- Phase 3 (APScheduler setup): 20 minutes
- Phase 4 (Integration): 5 minutes
- Phase 5 (Configuration): 2 minutes
- Phase 6 (Missing texts): 3 minutes
- Testing: 25 minutes
- **Total: ~77 minutes**

## Benefits

1. **Automatic payment processing:** No manual intervention needed
2. **Better UX:** Users get product even if forget to click button
3. **User notifications:** Clear feedback when payment auto-completes
4. **Clean up stale payments:** EXPIRED status prevents confusion
5. **Complete deposit flow:** Balance top-ups will work automatically (future)
6. **Logging:** Full audit trail of all payment transitions
7. **Extensible:** APScheduler allows adding more periodic tasks later
"""Background scheduler for periodic tasks."""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.config import settings
from src.infrastructure.database import async_session_maker
from src.bot.bot import bot
from src.models.payment import Payment, PaymentStatus
from src.services.payment import PaymentService
from src.bot.texts import Texts

logger = logging.getLogger(__name__)


scheduler = AsyncIOScheduler()


async def check_pending_payments_job() -> None:
    """Job to check stale PENDING payments.

    Called by APScheduler every PAYMENT_CHECK_INTERVAL_MINUTES.
    """
    expiry_timeout_hours = getattr(settings, "payment_expiry_timeout_hours", 1)
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

    payment = await payment_service.check_and_update_status(payment)

    if payment.status == PaymentStatus.COMPLETED:
        logger.info(
            f"Stale payment completed successfully",
            extra={
                "payment_id": str(payment.id),
                "status": payment.status.value,
            },
        )

        try:
            user = await payment_service.user_repository.get_by_id(payment.user_id)
            if user:
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
        await bot.send_message(
            telegram_id,
            Texts.PAYMENT_AUTO_COMPLETED.format(amount=amount),
            parse_mode="HTML",
        )

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
                Texts.BALANCE_TOPUP_SUCCESS.format(
                    amount=delivery_result["amount"],
                    balance=delivery_result["new_balance"],
                ),
                parse_mode="HTML",
            )

        logger.info(
            f"User notified about auto-completed payment",
            extra={
                "telegram_id": telegram_id,
                "amount": str(amount),
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
    check_interval_minutes = getattr(settings, "payment_check_interval_minutes", 5)

    logger.info(
        f"Setting up scheduler",
        extra={"check_interval_minutes": check_interval_minutes},
    )

    scheduler.add_job(
        check_pending_payments_job,
        trigger=IntervalTrigger(minutes=check_interval_minutes),
        id="payment_checker",
        name="Check stale PENDING payments",
        max_instances=1,
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

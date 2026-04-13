"""Background scheduler for periodic tasks."""

import logging
from datetime import UTC, datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.bot.bot import bot
from src.bot.keyboards import Keyboards
from src.bot.texts import Texts
from src.config import settings
from src.infrastructure.database import async_session_maker
from src.models.payment import Payment, PaymentStatus
from src.services.payment import PaymentService
from src.services.subscription import SubscriptionService

logger = logging.getLogger(__name__)


scheduler = AsyncIOScheduler()


MSK_TZ = timezone(timedelta(hours=3))


async def check_pending_payments_job() -> None:
    """Job to check and process PENDING payments.

    Called by APScheduler every PAYMENT_CHECK_INTERVAL_MINUTES.

    Logic:
    - Payments older than expiry_timeout_hours → mark as EXPIRED
    - Payments newer than expiry_timeout_hours → check status with provider
    """
    expiry_timeout_hours = getattr(settings, "payment_expiry_timeout_hours", 1)
    threshold = datetime.now(UTC) - timedelta(hours=expiry_timeout_hours)

    logger.info(
        "Checking PENDING payments",
        extra={
            "threshold": threshold.isoformat(),
            "expiry_timeout_hours": expiry_timeout_hours,
        },
    )

    async with async_session_maker() as session:
        payment_service = PaymentService(session)

        # Step 1: Mark expired payments (older than timeout)
        expired_payments = await payment_service.repository.get_expired_pending_payments(
            older_than=threshold,
            limit=100,
        )

        if expired_payments:
            logger.info(
                f"Found {len(expired_payments)} expired PENDING payments (older than {expiry_timeout_hours}h)",
                extra={"expired_count": len(expired_payments)},
            )

            for payment in expired_payments:
                try:
                    await mark_payment_as_expired(payment_service, payment)
                except Exception as e:
                    logger.error(
                        f"Failed to mark payment as expired: {e}",
                        extra={
                            "payment_id": str(payment.id),
                            "user_id": str(payment.user_id),
                        },
                        exc_info=True,
                    )

        # Step 2: Check active payments (newer than timeout)
        active_payments = await payment_service.repository.get_active_pending_payments(
            newer_than=threshold,
            limit=100,
        )

        if not active_payments:
            logger.debug("No active PENDING payments found")
            return

        logger.info(
            f"Found {len(active_payments)} active PENDING payments (newer than {expiry_timeout_hours}h)",
            extra={"active_count": len(active_payments)},
        )

        for payment in active_payments:
            try:
                await process_active_payment(payment_service, payment)
            except Exception as e:
                logger.error(
                    f"Failed to process payment {payment.id}: {e}",
                    extra={
                        "payment_id": str(payment.id),
                        "user_id": str(payment.user_id),
                    },
                    exc_info=True,
                )


async def mark_payment_as_expired(
    payment_service: PaymentService,
    payment: Payment,
) -> None:
    """Mark payment as EXPIRED without checking provider.

    Args:
        payment_service: PaymentService instance
        payment: Payment to mark as expired
    """
    logger.info(
        "Marking payment as expired",
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
        "Payment marked as expired",
        extra={
            "payment_id": str(payment.id),
            "status": payment.status.value,
        },
    )


async def process_active_payment(
    payment_service: PaymentService,
    payment: Payment,
) -> None:
    """Process one active PENDING payment (check status with provider).

    Args:
        payment_service: PaymentService instance
        payment: Payment to process
    """
    logger.info(
        "Processing active payment",
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
            "Active payment completed successfully",
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
                    "Product delivered for active payment",
                    extra={
                        "payment_id": str(payment.id),
                        "delivery_type": delivery_result.get("type"),
                    },
                )

                await notify_user_payment_completed(
                    telegram_id=user.telegram_id,
                    amount=str(payment.amount),
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
            "Active payment failed",
            extra={
                "payment_id": str(payment.id),
                "status": payment.status.value,
            },
        )

    elif payment.status == PaymentStatus.CANCELLED:
        logger.warning(
            "Active payment cancelled",
            extra={
                "payment_id": str(payment.id),
                "status": payment.status.value,
            },
        )

    elif payment.status == PaymentStatus.PENDING:
        # Still pending after check - will be checked again next run
        logger.debug(
            "Active payment still pending",
            extra={
                "payment_id": str(payment.id),
                "created_at": payment.created_at.isoformat(),
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
            "User notified about auto-completed payment",
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


async def check_expiring_subscriptions_job() -> None:
    """Job to check and notify users about expiring subscriptions.

    Called by APScheduler every SUBSCRIPTION_EXPIRY_CHECK_INTERVAL_HOURS.
    Finds subscriptions expiring within a specific window and sends notifications.
    """
    hours_before = getattr(settings, "subscription_expiry_notify_hours", 24)
    check_interval = getattr(settings, "subscription_expiry_check_interval_hours", 1)

    logger.info(
        f"Checking for subscriptions expiring in window [{hours_before - check_interval}, {hours_before}] hours",
        extra={"hours_before": hours_before, "check_interval": check_interval},
    )

    async with async_session_maker() as session:
        subscription_service = SubscriptionService(session)

        expiring_subscriptions = await subscription_service.repository.get_expiring_subscriptions(
            hours_before=hours_before, check_interval_hours=check_interval, limit=100
        )

        if not expiring_subscriptions:
            logger.debug("No expiring subscriptions found in the window")
            return

        logger.info(
            f"Found {len(expiring_subscriptions)} subscriptions expiring in the window",
            extra={"count": len(expiring_subscriptions)},
        )

        for subscription in expiring_subscriptions:
            try:
                user = subscription.user
                if not user or not user.telegram_id:
                    logger.warning(
                        f"Subscription {subscription.id} has no user or telegram_id",
                        extra={"subscription_id": str(subscription.id)},
                    )
                    continue

                product = subscription.product
                subscription_type = product.subscription_type if product else "unknown"

                # Convert end_date to Moscow time
                end_date_msk = subscription.end_date.astimezone(MSK_TZ)
                end_date_str = end_date_msk.strftime("%d.%m.%Y %H:%M")

                await bot.send_message(
                    user.telegram_id,
                    Texts.SUBSCRIPTION_EXPIRING.format(
                        end_date=f"{end_date_str} (МСК)",
                        subscription_type=subscription_type,
                    ),
                    parse_mode="HTML",
                    reply_markup=Keyboards.main_menu(show_trial_button=False),
                )

                logger.info(
                    "Sent expiry notification to user",
                    extra={
                        "user_id": str(user.id),
                        "telegram_id": user.telegram_id,
                        "subscription_id": str(subscription.id),
                        "end_date": subscription.end_date.isoformat(),
                        "end_date_msk": end_date_msk.isoformat(),
                    },
                )

            except Exception as e:
                logger.error(
                    f"Failed to send expiry notification: {e}",
                    extra={
                        "subscription_id": str(subscription.id),
                        "user_id": str(subscription.user_id) if subscription.user_id else None,
                    },
                    exc_info=True,
                )


def setup_scheduler() -> None:
    """Setup APScheduler with payment checker job."""
    check_interval_minutes = getattr(settings, "payment_check_interval_minutes", 5)
    expiry_check_interval_hours = getattr(settings, "subscription_expiry_check_interval_hours", 1)

    logger.info(
        "Setting up scheduler",
        extra={
            "check_interval_minutes": check_interval_minutes,
            "expiry_check_interval_hours": expiry_check_interval_hours,
        },
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

    scheduler.add_job(
        check_expiring_subscriptions_job,
        trigger=IntervalTrigger(hours=expiry_check_interval_hours),
        id="subscription_expiry_checker",
        name="Check expiring subscriptions",
        max_instances=1,
        replace_existing=True,
    )

    logger.info(
        f"Subscription expiry checker job scheduled every {expiry_check_interval_hours} hours"
    )


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

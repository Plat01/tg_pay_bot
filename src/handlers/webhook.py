"""Webhook handler for Platega payment notifications.

This module provides an aiohttp-based webhook endpoint for receiving
payment status updates from Platega payment provider.
"""

import asyncio
import logging
from typing import Any

from aiohttp import web

from src.config import settings
from src.infrastructure.database import async_session_maker
from src.infrastructure.payments import (
    PaymentProviderFactory,
    PaymentSignatureError,
    PaymentValidationError,
    PaymentStatus,
)
from src.infrastructure.payments.platega import PlategaProvider
from src.models.payment import PaymentStatus as ModelPaymentStatus
from src.services.payment import PaymentService

logger = logging.getLogger(__name__)


async def handle_platega_webhook(request: web.Request) -> web.Response:
    """Handle webhook notification from Platega.

    This endpoint receives POST requests from Platega when a payment
    status changes (e.g., payment confirmed, cancelled, etc.).

    Args:
        request: aiohttp web request with webhook payload

    Returns:
        web.Response: HTTP response (200 for success, 400 for validation errors)

    Flow:
        1. Get raw body and headers
        2. Verify signature
        3. Parse webhook data
        4. Find payment by external_id
        5. Update payment status
        6. If paid - update user balance and process referral
        7. Send notification to user via Telegram bot
    """
    # Get raw body for signature verification
    raw_body = await request.read()
    headers = dict(request.headers)

    # Create Platega provider instance
    provider = PaymentProviderFactory.create_default()

    try:
        # Parse and validate webhook data
        webhook_data = provider.parse_webhook(raw_body, headers)

        logger.info(
            f"Received Platega webhook: payment_id={webhook_data.payment_id}, "
            f"order_id={webhook_data.order_id}, status={webhook_data.status}"
        )

    except PaymentSignatureError as e:
        logger.warning(f"Webhook signature verification failed: {e}")
        return web.Response(status=401, text="Invalid signature")

    except PaymentValidationError as e:
        logger.error(f"Webhook validation error: {e}")
        return web.Response(status=400, text="Invalid webhook data")

    except Exception as e:
        logger.error(f"Unexpected webhook error: {e}")
        return web.Response(status=500, text="Internal server error")

    # Process payment status update
    try:
        async with async_session_maker() as session:
            payment_service = PaymentService(session)

            # Find payment by external_id (Platega transaction ID)
            payment = await payment_service.get_payment_by_external_id(
                webhook_data.payment_id
            )

            if payment is None:
                logger.warning(
                    f"Payment not found for external_id: {webhook_data.payment_id}"
                )
                # Return 200 to prevent retries for unknown payments
                return web.Response(status=200, text="Payment not found")

            # Check if payment is already processed (idempotency)
            if payment.status != ModelPaymentStatus.PENDING:
                logger.info(
                    f"Payment {payment.id} already processed with status: {payment.status}"
                )
                return web.Response(status=200, text="Payment already processed")

            # Update payment status based on webhook
            if webhook_data.status == PaymentStatus.PAID:
                # Mark payment as completed and process referral
                await payment_service.complete_payment(payment)
                logger.info(f"Payment {payment.id} completed successfully")

                # Notify user via bot (if bot is available)
                await notify_user_payment_success(payment.user_id, payment)

            elif webhook_data.status == PaymentStatus.CANCELLED:
                await payment_service.cancel_payment(payment)
                logger.info(f"Payment {payment.id} cancelled")

            elif webhook_data.status == PaymentStatus.FAILED:
                await payment_service.fail_payment(payment)
                logger.info(f"Payment {payment.id} failed")

            elif webhook_data.status == PaymentStatus.EXPIRED:
                await payment_service.cancel_payment(payment)
                logger.info(f"Payment {payment.id} expired")

            else:
                logger.info(f"Payment {payment.id} status: {webhook_data.status}")

        return web.Response(status=200, text="OK")

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        # Return 500 to trigger retry from Platega
        return web.Response(status=500, text="Internal error")


async def notify_user_payment_success(user_id: int, payment: Any) -> None:
    """Send notification to user about successful payment.

    Args:
        user_id: Telegram user ID
        payment: Payment model instance
    """
    try:
        from src.bot.bot import bot

        if bot is None:
            logger.warning("Bot not available for notification")
            return

        # Get user balance from payment service
        async with async_session_maker() as session:
            from src.services.user import UserService
            user_service = UserService(session)
            user = await user_service.get_by_telegram_id(user_id)

            if user is None:
                logger.warning(f"User not found for telegram_id: {user_id}")
                return

            # Send notification
            await bot.send_message(
                user_id,
                f"✅ Payment successful!\n\n"
                f"Amount: {payment.amount} {payment.currency}\n"
                f"Your balance: {user.balance} {payment.currency}\n\n"
                f"Thank you for your payment!",
            )

    except Exception as e:
        logger.error(f"Failed to send notification to user {user_id}: {e}")


def create_webhook_app() -> web.Application:
    """Create aiohttp application for webhook handling.

    Returns:
        web.Application with webhook routes configured
    """
    app = web.Application()

    # Register webhook routes
    app.router.add_post(
        "/webhook/platega",
        handle_platega_webhook,
    )

    # Health check endpoint
    async def health_check(request: web.Request) -> web.Response:
        return web.Response(status=200, text="OK")

    app.router.add_get("/health", health_check)

    return app


async def run_webhook_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Run webhook server.

    This function starts an aiohttp server for receiving webhook notifications.

    Args:
        host: Server host address
        port: Server port
    """
    app = create_webhook_app()
    runner = web.AppRunner(app)

    await runner.setup()
    site = web.TCPSite(runner, host, port)

    logger.info(f"Starting webhook server on {host}:{port}")

    await site.start()

    # Keep server running
    try:
        while True:
            await asyncio.sleep(3600)  # Sleep for 1 hour, then loop
    except asyncio.CancelledError:
        logger.info("Webhook server stopped")
    finally:
        await runner.cleanup()
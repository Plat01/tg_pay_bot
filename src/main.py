"""Main entry point for the Telegram bot."""

import asyncio
import logging

from src.config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.ERROR,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from aiogram.enums import ParseMode

from src.bot.bot import bot, dp
from src.services.payment_methods import PaymentMethodsService
from src.services.tariff import TariffService
from src.workers.scheduler import start_scheduler, shutdown_scheduler

logger = logging.getLogger(__name__)


def build_restart_message() -> str:
    """Build the restart notification text with available payment methods.

    Returns:
        Message text for admins.
    """
    methods = PaymentMethodsService.get_available_methods()

    if not methods:
        return (
            "Бот успешно перезапущен\n\n"
            "⚠️ Нет доступных способов оплаты: платежные провайдеры "
            "не настроены или недоступны"
        )

    methods_text = "\n".join(f"• {method.label} ({method.provider})" for method in methods)
    return f"Бот успешно перезапущен\n\nДоступные способы оплаты:\n{methods_text}"


async def notify_admins() -> None:
    """Send restart notification to all admins."""
    if not settings.admin_id_list:
        logger.warning("No admin IDs configured, skipping admin notification")
        return

    message_text = build_restart_message()

    for admin_id in settings.admin_id_list:
        try:
            await bot.send_message(admin_id, message_text)
            logger.info(f"Restart notification sent to admin {admin_id}")
        except Exception as e:
            logger.error(f"Failed to send restart notification to admin {admin_id}: {e}")


async def main() -> None:
    """Start the bot."""
    logger.info("Starting bot...")

    # Initialize tariff cache
    await TariffService.initialize_cache()
    logger.info("Tariff cache initialized")

    # Check which payment providers are configured and reachable:
    # only their methods are shown in the keyboards
    available_methods = await PaymentMethodsService.initialize_cache()
    if available_methods:
        logger.info(f"Payment methods available: {len(available_methods)}")
    else:
        logger.error("No payment methods available, only balance payments will work")

    start_scheduler()
    logger.info("Scheduler started")

    await notify_admins()

    try:
        await dp.start_polling(bot, parse_mode=ParseMode.HTML)
    finally:
        shutdown_scheduler()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

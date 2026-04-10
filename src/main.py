"""Main entry point for the Telegram bot."""

import asyncio
import logging

from src.config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from aiogram.enums import ParseMode

from src.bot.bot import bot, dp
from src.workers.scheduler import start_scheduler, shutdown_scheduler

logger = logging.getLogger(__name__)


async def notify_admins() -> None:
    """Send restart notification to all admins."""
    if not settings.admin_id_list:
        logger.warning("No admin IDs configured, skipping admin notification")
        return

    for admin_id in settings.admin_id_list:
        try:
            await bot.send_message(admin_id, "Бот успешно перезапущен")
            logger.info(f"Restart notification sent to admin {admin_id}")
        except Exception as e:
            logger.error(f"Failed to send restart notification to admin {admin_id}: {e}")


async def main() -> None:
    """Start the bot."""
    logger.info("Starting bot...")

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

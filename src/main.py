"""Main entry point for the Telegram bot."""

import asyncio
import logging

from src.config import settings

# Configure logging BEFORE imports that use logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from aiogram.enums import ParseMode

from src.bot.bot import bot, dp

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

    # Notify admins about restart
    await notify_admins()

    # Start polling
    try:
        await dp.start_polling(bot, parse_mode=ParseMode.HTML)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

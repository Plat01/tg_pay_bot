"""Bot initialization and setup."""

from aiogram import Bot, Dispatcher

from src.config import settings
from src.handlers import register_handlers

# Initialize bot and dispatcher
bot = Bot(token=settings.bot_token)
dp = Dispatcher()

# Register all handlers
register_handlers(dp)
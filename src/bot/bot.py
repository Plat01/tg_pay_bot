"""Bot initialization and setup."""

import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from src.bot.handlers import register_handlers
from src.config import settings

logger = logging.getLogger(__name__)

proxy_url = settings.proxy_url or os.environ.get("ALL_PROXY") or os.environ.get("all_proxy")

if proxy_url:
    logger.info(f"Using proxy: {proxy_url[:30]}***")
    session = AiohttpSession(proxy=proxy_url)
    bot = Bot(token=settings.bot_token, session=session)
else:
    logger.info("Running without proxy")
    bot = Bot(token=settings.bot_token)
dp = Dispatcher()

register_handlers(dp)

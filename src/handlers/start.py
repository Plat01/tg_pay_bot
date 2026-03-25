"""Start command handler for user registration."""

import logging

from aiogram import Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

from src.db.session import async_session_maker
from src.services.user import UserService

logger = logging.getLogger(__name__)


async def cmd_start(message: Message) -> None:
    """Handle /start command - register or welcome back user."""
    # Extract referral code from command arguments
    args = message.text.split() if message.text else []
    referral_code = args[1] if len(args) > 1 else None

    async with async_session_maker() as session:
        user_service = UserService(session)

        # Get user info from message
        user = message.from_user
        if not user:
            await message.answer("Error: Could not get user info")
            return

        # Register or update user
        db_user = await user_service.get_or_create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language_code=user.language_code,
            is_bot=user.is_bot,
            is_premium=getattr(user, "is_premium", False),
            referral_code=referral_code,
        )

        # Build welcome message
        is_new_user = db_user.created_at == db_user.updated_at

        if is_new_user:
            # New user
            welcome_text = (
                f"🎉 Welcome, {user.first_name or 'User'}!\n\n"
                f"You have been successfully registered.\n"
                f"Your referral code: <code>{db_user.referral_code}</code>\n\n"
                f"Share your referral code with friends and earn "
                f"{10}% from their payments!"
            )
            logger.info(f"New user registered: {user.id} (@{user.username})")
        else:
            # Existing user
            welcome_text = (
                f"👋 Welcome back, {user.first_name or 'User'}!\n\n"
                f"Your referral code: <code>{db_user.referral_code}</code>\n"
                f"Your balance: {db_user.balance} RUB"
            )
            logger.info(f"User logged in: {user.id} (@{user.username})")

        await message.answer(welcome_text, parse_mode="HTML")


def register_start_handlers(dp: Dispatcher) -> None:
    """Register start command handlers."""
    dp.message.register(cmd_start, CommandStart())
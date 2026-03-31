"""Start command handler for user registration and main menu handlers."""

import logging

from aiogram import Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from src.bot.keyboards import Keyboards
from src.bot.texts import Texts
from src.config import settings
from src.infrastructure.database import async_session_maker
from src.services.user import UserService

logger = logging.getLogger(__name__)


async def cmd_start(message: Message) -> None:
    """Handle /start command - register or welcome back user.

    Shows main menu keyboard with buttons for balance, deposit,
    referral, and help.
    """
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
            # New user - show welcome message
            welcome_text = (
                f"👋 Добро пожаловать, {user.first_name or 'пользователь'}!\n\n"
                f"Вы успешно зарегистрированы.\n\n"
                f"Используйте кнопки меню для управления:\n"
                f"• 💰 Баланс — проверить баланс\n"
                f"• ➕ Пополнить — пополнить баланс\n"
                f"• 👥 Пригласить друга — реферальная программа\n"
                f"• 📖 Помощь — справка по командам"
            )
            logger.info(f"New user registered: {user.id} (@{user.username})")
        else:
            # Existing user - show welcome back message
            welcome_text = (
                f"👋 С возвращением, {user.first_name or 'пользователь'}!\n\n"
                f"Ваш баланс: {db_user.balance} ₽\n\n"
                f"Используйте кнопки меню для управления."
            )
            logger.info(f"User logged in: {user.id} (@{user.username})")

        # Send welcome message with main menu keyboard
        await message.answer(
            welcome_text,
            reply_markup=Keyboards.main_menu(),
        )


async def handle_balance_button(message: Message) -> None:
    """Handle 💰 Баланс button from main menu."""
    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(message.from_user.id)

        if not user:
            await message.answer(
                "❌ Вы не зарегистрированы.\n"
                "Используйте /start для регистрации.",
                reply_markup=Keyboards.main_menu(),
            )
            return

        await message.answer(
            f"💰 <b>Ваш баланс</b>\n\n"
            f"Сумма: {user.balance} ₽\n"
            f"Реферальный код: <code>{user.referral_code}</code>\n\n"
            f"Для пополнения используйте кнопку ➕ Пополнить",
            parse_mode="HTML",
            reply_markup=Keyboards.main_menu(),
        )


async def handle_deposit_button(message: Message) -> None:
    """Handle ➕ Пополнить button from main menu.

    Redirects to deposit flow.
    """
    # Import deposit handler to start deposit flow
    from src.bot.handlers.deposit import cmd_deposit
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage

    # Create a fake state context for the deposit flow
    # Note: This will be handled properly by the FSM middleware
    await message.answer(
        "💳 <b>Пополнение баланса</b>\n\n"
        "Для пополнения используйте команду /deposit\n"
        "или нажмите на кнопку ниже:",
        parse_mode="HTML",
        reply_markup=Keyboards.main_menu(),
    )


async def handle_referral_button(message: Message) -> None:
    """Handle 👥 Пригласить друга button from main menu.

    Shows referral information with invite link and share button.
    """
    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(message.from_user.id)

        if not user:
            await message.answer(
                "❌ Вы не зарегистрированы.\n"
                "Используйте /start для регистрации.",
                reply_markup=Keyboards.main_menu(),
            )
            return

        # Build referral link
        referral_link = f"{settings.bot_link}?start={user.referral_code}"

        # Format referral info message
        referral_text = Texts.REFERRAL_INFO.format(
            bot_link=settings.bot_link,
            referral_code=user.referral_code,
        )

        # Send referral info with invite keyboard
        await message.answer(
            referral_text,
            parse_mode="HTML",
            reply_markup=Keyboards.referral_invite(referral_link),
        )


async def handle_help_button(message: Message) -> None:
    """Handle 📖 Помощь button from main menu."""
    await message.answer(
        Texts.HELP_TEXT,
        parse_mode="HTML",
        reply_markup=Keyboards.main_menu(),
    )


def register_start_handlers(dp: Dispatcher) -> None:
    """Register start command and main menu button handlers."""
    # Command handlers
    dp.message.register(cmd_start, CommandStart())

    # Reply keyboard button handlers
    dp.message.register(handle_balance_button, F.text == "💰 Баланс")
    dp.message.register(handle_deposit_button, F.text == "➕ Пополнить")
    dp.message.register(handle_referral_button, F.text == "👥 Пригласить друга")
    dp.message.register(handle_help_button, F.text == "📖 Помощь")

    logger.info("Start and main menu handlers registered")
"""Start command handler for user registration and main menu handlers."""

import logging

from aiogram import Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards import Keyboards
from src.bot.texts import Texts
from src.config import settings
from src.infrastructure.database import async_session_maker
from src.services.user import UserService

logger = logging.getLogger(__name__)


async def cmd_start(message: Message) -> None:
    """Handle /start command - register or welcome back user.

    Shows main menu inline keyboard with buttons under message.
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
                f"👋 <b>Добро пожаловать, {user.first_name or 'пользователь'}!</b>\n\n"
                f"Вы успешно зарегистрированы.\n\n"
                f"Используйте кнопки меню для управления:"
            )
            logger.info(f"New user registered: {user.id} (@{user.username})")
        else:
            # Existing user - show welcome back message
            welcome_text = (
                f"👋 <b>С возвращением, {user.first_name or 'пользователь'}!</b>\n\n"
                f"Ваш баланс: {db_user.balance} ₽\n\n"
                f"Используйте кнопки меню для управления:"
            )
            logger.info(f"User logged in: {user.id} (@{user.username})")

        # Send welcome message with main menu inline keyboard
        await message.answer(
            welcome_text,
            parse_mode="HTML",
            reply_markup=Keyboards.main_menu(),
        )


async def handle_main_menu_callback(callback: CallbackQuery) -> None:
    """Handle 'Назад' button - return to main menu."""
    user = callback.from_user

    async with async_session_maker() as session:
        user_service = UserService(session)
        db_user = await user_service.get_user_by_telegram_id(user.id)

        if not db_user:
            await callback.message.edit_text(
                "❌ Вы не зарегистрированы.\n"
                "Используйте /start для регистрации.",
                reply_markup=None,
            )
            await callback.answer()
            return

        welcome_text = (
            f"👋 <b>Главное меню</b>\n\n"
            f"Ваш баланс: {db_user.balance} ₽\n\n"
            f"Используйте кнопки меню для управления:"
        )

        await callback.message.edit_text(
            welcome_text,
            parse_mode="HTML",
            reply_markup=Keyboards.main_menu(),
        )
        await callback.answer()


async def handle_balance_callback(callback: CallbackQuery) -> None:
    """Handle 💰 Баланс button from main menu."""
    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)

        if not user:
            await callback.message.edit_text(
                "❌ Вы не зарегистрированы.\n"
                "Используйте /start для регистрации.",
                reply_markup=Keyboards.back_to_menu(),
            )
            await callback.answer()
            return

        balance_text = Texts.BALANCE_INFO.format(
            balance=user.balance,
            referral_code=user.referral_code,
        )

        await callback.message.edit_text(
            balance_text,
            parse_mode="HTML",
            reply_markup=Keyboards.balance_actions(),
        )
        await callback.answer()


async def handle_deposit_callback(callback: CallbackQuery) -> None:
    """Handle ➕ Пополнить button from main menu.

    Redirects to deposit flow.
    """
    await callback.message.edit_text(
        "💳 <b>Пополнение баланса</b>\n\n"
        "Для пополнения используйте команду /deposit",
        parse_mode="HTML",
        reply_markup=Keyboards.back_to_menu(),
    )
    await callback.answer()


async def handle_referral_callback(callback: CallbackQuery) -> None:
    """Handle 👥 Пригласить друга button from main menu.

    Shows referral information with invite link and share button.
    """
    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)

        if not user:
            await callback.message.edit_text(
                "❌ Вы не зарегистрированы.\n"
                "Используйте /start для регистрации.",
                reply_markup=Keyboards.back_to_menu(),
            )
            await callback.answer()
            return

        # Build referral link
        referral_link = f"{settings.bot_link}?start={user.referral_code}"

        # Format referral info message
        referral_text = Texts.REFERRAL_INFO.format(
            bot_link=settings.bot_link,
            referral_code=user.referral_code,
        )

        # Send referral info with invite keyboard
        await callback.message.edit_text(
            referral_text,
            parse_mode="HTML",
            reply_markup=Keyboards.referral_invite(referral_link),
        )
        await callback.answer()


async def handle_help_callback(callback: CallbackQuery) -> None:
    """Handle 📖 Помощь button from main menu."""
    await callback.message.edit_text(
        Texts.HELP_TEXT,
        parse_mode="HTML",
        reply_markup=Keyboards.back_to_menu(),
    )
    await callback.answer()


def register_start_handlers(dp: Dispatcher) -> None:
    """Register start command and main menu callback handlers."""
    from src.bot.constants import CallbackData

    # Command handlers
    dp.message.register(cmd_start, CommandStart())

    # Callback handlers for inline keyboard buttons
    dp.callback_query.register(
        handle_main_menu_callback,
        F.data == CallbackData.MAIN_MENU,
    )
    dp.callback_query.register(
        handle_balance_callback,
        F.data == CallbackData.BALANCE,
    )
    dp.callback_query.register(
        handle_deposit_callback,
        F.data == CallbackData.DEPOSIT,
    )
    dp.callback_query.register(
        handle_referral_callback,
        F.data == CallbackData.REFERRAL,
    )
    dp.callback_query.register(
        handle_help_callback,
        F.data == CallbackData.HELP,
    )

    logger.info("Start and main menu handlers registered")
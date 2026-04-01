"""Start command handler for user registration and main menu handlers."""

import logging

from aiogram import Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.constants import CallbackData
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
            telegram_id=str(user.id),
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
            welcome_text = Texts.START_NEW_USER.format(
                first_name=user.first_name or "пользователь",
            )
            logger.info(f"New user registered: {user.id} (@{user.username})")
        else:
            # Existing user - show welcome back message
            welcome_text = Texts.START_EXISTING_USER.format(
                first_name=user.first_name or "пользователь",
                balance=db_user.balance,
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
        db_user = await user_service.get_user_by_telegram_id(str(user.id))

        if not db_user:
            await callback.message.edit_text(
                Texts.ERROR_NOT_REGISTERED,
                reply_markup=None,
            )
            await callback.answer()
            return

        welcome_text = Texts.START_MAIN_MENU.format(balance=db_user.balance)

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
        user = await user_service.get_user_by_telegram_id(str(callback.from_user.id))

        if not user:
            await callback.message.edit_text(
                Texts.ERROR_NOT_REGISTERED,
                reply_markup=Keyboards.back_to_menu(),
            )
            await callback.answer()
            return

        balance_text = Texts.BALANCE_INFO.format(
            balance=user.balance,
            referral_code=user.referral_code,
        )

        # Send balance info with deposit amount buttons
        await callback.message.edit_text(
            balance_text,
            parse_mode="HTML",
            reply_markup=Keyboards.balance_actions(),
        )
        await callback.answer()
        
        # Send deposit prompt with amount buttons
        await callback.message.answer(
            Texts.BALANCE_DEPOSIT_PROMPT,
            parse_mode="HTML",
            reply_markup=Keyboards.balance_deposit_amounts(),
        )


async def handle_deposit_callback(callback: CallbackQuery) -> None:
    """Handle ➕ Пополнить button from main menu.

    Redirects to deposit flow with amount selection keyboard.
    """
    from src.bot.handlers.deposit import MIN_DEPOSIT_AMOUNT
    
    await callback.message.edit_text(
        Texts.DEPOSIT_START.format(min_amount=MIN_DEPOSIT_AMOUNT),
        parse_mode="HTML",
        reply_markup=Keyboards.balance_deposit_amounts(),
    )
    await callback.answer()


async def handle_referral_callback(callback: CallbackQuery) -> None:
    """Handle 👥 Пригласить друга button from main menu.

    Shows referral information with invite link and share button.
    """
    async with async_session_maker() as session:
        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(str(callback.from_user.id))

        if not user:
            await callback.message.edit_text(
                Texts.ERROR_NOT_REGISTERED,
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


async def handle_trial_subscription_callback(callback: CallbackQuery) -> None:
    """Handle 🧪 Тестовая подписка button from main menu."""
    await callback.message.edit_text(
        Texts.TRIAL_SUBSCRIPTION,
        parse_mode="HTML",
        reply_markup=Keyboards.trial_subscription(),
    )
    await callback.answer()


async def handle_buy_subscription_callback(callback: CallbackQuery) -> None:
    """Handle 💎 Купить подписку button from main menu."""
    await callback.message.edit_text(
        Texts.BUY_SUBSCRIPTION,
        parse_mode="HTML",
        reply_markup=Keyboards.buy_subscription(),
    )
    await callback.answer()


async def handle_deposit_amount_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle deposit amount selection from balance screen.
    
    Starts deposit flow with selected amount.
    """
    from src.bot.handlers.deposit import (
        DepositStates,
        process_amount_preset,
    )
    
    # Parse amount from callback data
    amount_map = {
        CallbackData.DEPOSIT_AMOUNT_50: 50,
        CallbackData.DEPOSIT_AMOUNT_100: 100,
        CallbackData.DEPOSIT_AMOUNT_250: 250,
        CallbackData.DEPOSIT_AMOUNT_500: 500,
        CallbackData.DEPOSIT_AMOUNT_1000: 1000,
        CallbackData.DEPOSIT_AMOUNT_2500: 2500,
    }
    
    amount = amount_map.get(callback.data)
    if not amount:
        await callback.answer("❌ Неверная сумма", show_alert=True)
        return
    
    # Set FSM state and process amount
    await state.set_state(DepositStates.amount)
    
    # Create a mock callback with data in format "amount:{amount}"
    original_data = callback.data
    callback.data = f"amount:{amount}"
    
    # Call the deposit handler
    await process_amount_preset(callback, state)
    
    # Restore original callback data
    callback.data = original_data


def register_start_handlers(dp: Dispatcher) -> None:
    """Register start command and main menu callback handlers."""
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
    dp.callback_query.register(
        handle_trial_subscription_callback,
        F.data == CallbackData.TRIAL_SUBSCRIPTION,
    )
    dp.callback_query.register(
        handle_buy_subscription_callback,
        F.data == CallbackData.BUY_SUBSCRIPTION,
    )
    dp.callback_query.register(
        handle_deposit_amount_callback,
        F.data.startswith("deposit_"),
    )

    logger.info("Start and main menu handlers registered")
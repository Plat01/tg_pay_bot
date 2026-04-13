"""Start command handler for user registration and main menu handlers."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

from aiogram import Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot.constants import CallbackData
from src.bot.keyboards import Keyboards
from src.bot.texts import Texts
from src.config import settings
from src.infrastructure.database import async_session_maker
from src.services.subscription import SubscriptionService
from src.services.tariff import TariffService
from src.services.user import UserService

logger = logging.getLogger(__name__)

MSK_TZ = ZoneInfo("Europe/Moscow")


async def cmd_start(message: Message) -> None:
    """Handle /start command - register or welcome back user.

    Shows main menu inline keyboard with buttons under message.
    """
    args = message.text.split() if message.text else []
    referral_code = args[1] if len(args) > 1 else None

    async with async_session_maker() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)

        user = message.from_user
        if not user:
            await message.answer("Error: Could not get user info")
            return

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

        subscriptions = await subscription_service.get_active_subscriptions(db_user.id)
        if subscriptions:
            subscription_status_list = []
            for i, sub in enumerate(subscriptions, 1):
                product = getattr(sub, "product", None)
                sub_info = subscription_service.get_subscription_info(sub)
                sub_type = product.subscription_type if product else "unknown"
                end_date_str = sub.end_date.astimezone(MSK_TZ).strftime("%d.%m.%Y %H:%M")
                time_left_str = f"{sub_info['days_left']} дн. / {sub_info['hours_left']} час."
                subscription_status_list.append(
                    f"{i}. {sub_type} — до {end_date_str} ({time_left_str})"
                )
            subscription_status = "\n".join(subscription_status_list)
            show_trial_button = False
        else:
            subscription_status = "❌ Не активна"
            show_trial_button = db_user.is_new

        await message.answer(
            Texts.START_WELCOME.format(
                subscription_status=subscription_status,
            ),
            parse_mode="HTML",
            reply_markup=Keyboards.main_menu(show_trial_button=show_trial_button),
        )

        logger.info(f"User started bot: {user.id} (@{user.username})")


async def handle_main_menu_callback(callback: CallbackQuery) -> None:
    """Handle 'Назад' button - return to main menu."""
    async with async_session_maker() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)

        db_user = await user_service.get_user_by_telegram_id(str(callback.from_user.id))

        if not db_user:
            await callback.message.edit_text(
                Texts.ERROR_NOT_REGISTERED,
                reply_markup=None,
            )
            await callback.answer()
            return

        subscriptions = await subscription_service.get_active_subscriptions(db_user.id)
        if subscriptions:
            subscription_status_list = []
            for i, sub in enumerate(subscriptions, 1):
                product = getattr(sub, "product", None)
                sub_info = subscription_service.get_subscription_info(sub)
                sub_type = product.subscription_type if product else "unknown"
                end_date_str = sub.end_date.astimezone(MSK_TZ).strftime("%d.%m.%Y %H:%M")
                time_left_str = f"{sub_info['days_left']} дн. / {sub_info['hours_left']} час."
                subscription_status_list.append(
                    f"{i}. {sub_type} — до {end_date_str} ({time_left_str})"
                )
            subscription_status = "\n".join(subscription_status_list)
            show_trial_button = False
        else:
            subscription_status = "❌ Не активна"
            show_trial_button = db_user.is_new

        await callback.message.edit_text(
            Texts.START_MAIN_MENU.format(
                subscription_status=subscription_status,
            ),
            parse_mode="HTML",
            reply_markup=Keyboards.main_menu(show_trial_button=show_trial_button),
        )
        await callback.answer()


async def handle_info_callback(callback: CallbackQuery) -> None:
    """Handle ℹ️ Инфо button from main menu."""
    await callback.message.edit_text(
        Texts.INFO_MENU_TEXT,
        parse_mode="HTML",
        reply_markup=Keyboards.info_menu(),
    )
    await callback.answer()


async def handle_profile_callback(callback: CallbackQuery) -> None:
    """Handle 💼 Профиль button from main menu."""
    async with async_session_maker() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)

        user = await user_service.get_user_by_telegram_id(str(callback.from_user.id))

        if not user:
            await callback.message.edit_text(
                Texts.ERROR_NOT_REGISTERED,
                reply_markup=Keyboards.back_to_menu(),
            )
            await callback.answer()
            return

        subscriptions = await subscription_service.get_active_subscriptions(user.id)

        name_parts = []
        if user.first_name:
            name_parts.append(user.first_name)
        if user.last_name:
            name_parts.append(user.last_name)
        display_name = " ".join(name_parts) if name_parts else (user.username or f"#{user.id}")

        if subscriptions:
            subscriptions_list = []
            for i, sub in enumerate(subscriptions, 1):
                product = getattr(sub, "product", None)
                sub_info = subscription_service.get_subscription_info(sub)
                sub_type = product.subscription_type if product else "unknown"
                end_date_str = sub.end_date.astimezone(MSK_TZ).strftime("%d.%m.%Y %H:%M")
                time_left_str = f"{sub_info['days_left']} дн. / {sub_info['hours_left']} час."
                subscriptions_list.append(f"{i}. {sub_type} — до {end_date_str} ({time_left_str})")

            profile_text = Texts.PROFILE_MULTIPLE_SUBSCRIPTIONS.format(
                username=display_name,
                balance=user.balance,
                subscriptions_list="\n".join(subscriptions_list),
            )

            await callback.message.edit_text(
                profile_text,
                parse_mode="HTML",
                reply_markup=Keyboards.subscription_links(subscriptions),
            )
        else:
            profile_text = Texts.PROFILE_NO_SUBSCRIPTION.format(
                username=display_name,
                balance=user.balance,
            )

            await callback.message.edit_text(
                profile_text,
                parse_mode="HTML",
                reply_markup=await Keyboards.buy_subscription(),
            )
        await callback.answer()


async def handle_pay_callback(callback: CallbackQuery) -> None:
    """Handle 💳 Оплатить button from main menu."""
    async with async_session_maker() as session:
        tariff_service = TariffService(session)
        tariffs = await tariff_service.get_all_tariffs()

    monthly_price = int(tariffs.get("monthly", {}).get("price", 199))
    quarterly_price = int(tariffs.get("quarterly", {}).get("price", 499))
    yearly_price = int(tariffs.get("yearly", {}).get("price", 1999))

    pay_text = (
        "💳 <b>Оплата подписки</b>\n\n"
        "Выберите тарифный план:\n\n"
        f"• 1 месяц — {monthly_price} ₽\n"
        f"• 3 месяца — {quarterly_price} ₽\n"
        f"• 12 месяцев — {yearly_price} ₽\n\n"
        "Для покупки выберите тариф."
    )

    await callback.message.edit_text(
        pay_text,
        parse_mode="HTML",
        reply_markup=await Keyboards.buy_subscription(),
    )
    await callback.answer()


async def handle_support_callback(callback: CallbackQuery) -> None:
    """Handle 🛠️ Поддержка button from main menu."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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

        # Format support text with user ID
        support_text = Texts.SUPPORT_TEXT.format(user_id=user.telegram_id)

        # Create keyboard with support link button
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💬 Перейти в поддержку", url=settings.support_link)],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
            ]
        )

        await callback.message.edit_text(
            support_text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        await callback.answer()


async def handle_bonuses_callback(callback: CallbackQuery) -> None:
    """Handle 🎁 Бонусы button from main menu."""
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

        # Check if user was referred (eligible for trial bonus)
        if user.referred_by_id:
            # User was referred - show bonus info with trial option
            await callback.message.edit_text(
                Texts.BONUSES_TEXT,
                parse_mode="HTML",
                reply_markup=Keyboards.trial_subscription(),
            )
        else:
            # User was not referred - show general bonus info
            await callback.message.edit_text(
                Texts.BONUSES_TEXT,
                parse_mode="HTML",
                reply_markup=Keyboards.back_to_menu(),
            )
        await callback.answer()


async def handle_connect_callback(callback: CallbackQuery) -> None:
    """Handle 👥 Пригласить друга button from main menu."""
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

        connect_text = Texts.CONNECT_TEXT.format(
            referral_link=referral_link,
        )

        # Add button to share referral link
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📤 Отправить друзьям",
                        switch_inline_query=referral_link,
                    )
                ],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
            ]
        )

        await callback.message.edit_text(
            connect_text,
            parse_mode="HTML",
            reply_markup=keyboard,
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
    """Handle 🧪 Тестовый период button from main menu."""
    async with async_session_maker() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)

        user = await user_service.get_user_by_telegram_id(str(callback.from_user.id))

        if not user:
            await callback.message.edit_text(
                Texts.ERROR_NOT_REGISTERED,
                reply_markup=Keyboards.back_to_menu(),
            )
            await callback.answer()
            return

        subscriptions = await subscription_service.get_active_subscriptions(user.id)

        if subscriptions or not user.is_new:
            await callback.message.edit_text(
                Texts.TRIAL_ALREADY_USED,
                parse_mode="HTML",
                reply_markup=await Keyboards.buy_subscription(),
            )
            await callback.answer()
            return

        await callback.message.edit_text(
            Texts.TRIAL_PROPOSAL,
            parse_mode="HTML",
            reply_markup=Keyboards.trial_subscription(),
        )
        await callback.answer()


async def handle_buy_subscription_callback(callback: CallbackQuery) -> None:
    """Handle 💎 Купить подписку button from main menu."""
    async with async_session_maker() as session:
        tariff_service = TariffService(session)
        tariffs = await tariff_service.get_all_tariffs()

    monthly_price = int(tariffs.get("monthly", {}).get("price", 199))
    quarterly_price = int(tariffs.get("quarterly", {}).get("price", 499))
    yearly_price = int(tariffs.get("yearly", {}).get("price", 1999))

    buy_text = (
        "💎 <b>Купить подписку</b>\n\n"
        "Выберите тарифный план:\n\n"
        f"• 1 месяц — {monthly_price} ₽\n"
        f"• 3 месяца — {quarterly_price} ₽\n"
        f"• 12 месяцев — {yearly_price} ₽\n\n"
        "Для покупки выберите тариф."
    )

    await callback.message.edit_text(
        buy_text,
        parse_mode="HTML",
        reply_markup=await Keyboards.buy_subscription(),
    )
    await callback.answer()


async def handle_trial_activate_callback(callback: CallbackQuery) -> None:
    """Handle ✅ Начать button - activate trial subscription."""
    from src.infrastructure.database.repositories import ProductRepository

    async with async_session_maker() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)
        product_repository = ProductRepository(session)

        user = await user_service.get_user_by_telegram_id(str(callback.from_user.id))

        if not user:
            await callback.message.edit_text(
                Texts.ERROR_NOT_REGISTERED,
                reply_markup=Keyboards.back_to_menu(),
            )
            await callback.answer()
            return

        subscriptions = await subscription_service.get_active_subscriptions(user.id)

        if subscriptions or not user.is_new:
            await callback.message.edit_text(
                Texts.TRIAL_ALREADY_USED,
                parse_mode="HTML",
                reply_markup=await Keyboards.buy_subscription(),
            )
            await callback.answer()
            return

        trial_product = await product_repository.get_product_by_subscription_type("trial")
        if not trial_product:
            await callback.message.edit_text(
                "❌ Тестовый VPN не найден. Обратитесь в поддержку.",
                parse_mode="HTML",
                reply_markup=Keyboards.error_with_support_link(),
            )
            await callback.answer()
            return

        await subscription_service.activate_trial(user.id)
        await user_service.mark_trial_used(user)

        await callback.message.edit_text(
            Texts.TRIAL_ACTIVATED.format(vpn_link=trial_product.happ_link),
            parse_mode="HTML",
            reply_markup=Keyboards.back_to_menu(),
        )
        await callback.answer()

        logger.info(f"User {user.telegram_id} activated trial subscription")


async def handle_get_subscription_link_callback(callback: CallbackQuery) -> None:
    """Handle get_sub_link callback - show VPN link for specific subscription."""
    async with async_session_maker() as session:
        subscription_service = SubscriptionService(session)

        subscription_id_str = callback.data.split(":")[1] if callback.data else None
        if not subscription_id_str:
            await callback.answer("❌ Ошибка: ID подписки не найден", show_alert=True)
            return

        import uuid

        try:
            subscription_id = uuid.UUID(subscription_id_str)
        except ValueError:
            await callback.answer("❌ Ошибка: неверный ID подписки", show_alert=True)
            return

        subscription = await subscription_service.get_active_subscription_by_id(subscription_id)

        if not subscription:
            await callback.answer("❌ Подписка не найдена или истекла", show_alert=True)
            return

        product = getattr(subscription, "product", None)
        if not product:
            await callback.answer("❌ Продукт подписки не найден", show_alert=True)
            return

        subscription_type = product.subscription_type
        end_date_str = subscription.end_date.astimezone(MSK_TZ).strftime("%d.%m.%Y %H:%M")
        vpn_link = product.happ_link

        await callback.message.edit_text(
            Texts.SUBSCRIPTION_LINK.format(
                subscription_type=subscription_type,
                end_date=end_date_str,
                vpn_link=f"<code>{vpn_link}</code>",
            ),
            parse_mode="HTML",
            reply_markup=Keyboards.back_to_menu(),
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

    # DEBUG: Log callback data to diagnose the issue
    logger.warning(f"DEBUG: callback.data = {callback.data!r}")
    logger.warning(f"DEBUG: callback type = {type(callback)}")

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
        logger.warning(f"DEBUG: Invalid callback data, amount not found")
        await callback.answer("❌ Неверная сумма", show_alert=True)
        return

    logger.warning(f"DEBUG: amount = {amount}")

    # Set FSM state and process amount
    await state.set_state(DepositStates.amount)

    # Create a mock callback with data in format "amount:{amount}"
    # WARNING: This will fail because CallbackQuery is frozen in aiogram 3.x
    original_data = callback.data
    logger.warning(
        f"DEBUG: Attempting to set callback.data from {original_data!r} to 'amount:{amount}'"
    )
    callback.data = f"amount:{amount}"

    # Call the deposit handler
    await process_amount_preset(callback, state)

    # Restore original callback data
    callback.data = original_data


def register_start_handlers(dp: Dispatcher) -> None:
    """Register start command and main menu callback handlers."""
    from src.bot.handlers.payment import register_payment_handlers

    # Command handlers
    dp.message.register(cmd_start, CommandStart())

    # Callback handlers for inline keyboard buttons
    dp.callback_query.register(
        handle_main_menu_callback,
        F.data == CallbackData.MAIN_MENU,
    )
    dp.callback_query.register(
        handle_info_callback,
        F.data == CallbackData.INFO,
    )
    dp.callback_query.register(
        handle_profile_callback,
        F.data == CallbackData.PROFILE,
    )
    dp.callback_query.register(
        handle_pay_callback,
        F.data == CallbackData.PAY,
    )
    dp.callback_query.register(
        handle_support_callback,
        F.data == CallbackData.SUPPORT,
    )
    dp.callback_query.register(
        handle_bonuses_callback,
        F.data == CallbackData.BONUSES,
    )
    dp.callback_query.register(
        handle_connect_callback,
        F.data == CallbackData.CONNECT,
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
        handle_trial_activate_callback,
        F.data == CallbackData.TRIAL_ACTIVATE,
    )
    dp.callback_query.register(
        handle_buy_subscription_callback,
        F.data == CallbackData.BUY_SUBSCRIPTION,
    )
    dp.callback_query.register(
        handle_deposit_amount_callback,
        F.data.startswith("deposit_"),
    )
    dp.callback_query.register(
        handle_get_subscription_link_callback,
        F.data.startswith(CallbackData.GET_SUBSCRIPTION_LINK),
    )

    # Register payment handlers
    register_payment_handlers(dp)

    logger.info("Start and main menu handlers registered")

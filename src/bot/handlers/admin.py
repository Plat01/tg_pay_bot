"""Admin command handlers for administrative functions."""

import logging
from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from src.config import settings
from src.bot.constants import Commands
from src.infrastructure.database import async_session_maker
from src.infrastructure.database.repositories import ProductRepository, UserRepository
from src.models.product import SubscriptionType

logger = logging.getLogger(__name__)


class SubscriptionLinkStates(StatesGroup):
    """States for collecting subscription links from admin."""

    waiting_for_trial_link = State()
    waiting_for_monthly_link = State()
    waiting_for_quarterly_link = State()
    waiting_for_yearly_link = State()


class BroadcastStates(StatesGroup):
    """States for broadcast message collection."""

    waiting_for_all_message = State()
    waiting_for_paid_message = State()


async def cmd_send_subscription_links(message: Message, state: FSMContext) -> None:
    """Admin command to collect subscription links.

    Only accessible to admin users defined in settings.admin_ids.
    Prompts admin to send trial, monthly, quarterly, and yearly links separately.
    """

    if not message.from_user:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    user_id = str(message.from_user.id)
    if user_id not in settings.admin_id_list:
        logger.warning(f"Non-admin user {user_id} tried to access admin command")
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    # Start the process of collecting links
    await state.set_state(SubscriptionLinkStates.waiting_for_trial_link)
    await message.answer(
        "🔗 <b>Введите ссылку для пробной (trial) подписки:</b>\n"
        "Для прекращения введите команду /cancel"
    )

    logger.info(f"Admin {user_id} started subscription links collection")


async def process_trial_link(message: Message, state: FSMContext) -> None:
    """Process the trial link sent by admin and save it immediately."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте ссылку текстом.")
        return

    trial_link = message.text.strip()

    # Save the trial link to database immediately
    try:
        async with async_session_maker() as session:
            product_repository = ProductRepository(session)

            # Deactivate existing trial product first (to update it)
            existing_products = await product_repository.get_all_products()
            for product in existing_products:
                if product.subscription_type == "trial":
                    await product_repository.update_product(product.id, is_active=False)

            # Create new trial product
            from src.models.product import Product

            trial_product = Product(
                subscription_type="trial",
                price=0.0,  # Trial is usually free
                duration_days=3,  # Default trial period
                device_limit=1,
                is_active=True,
                happ_link=trial_link,
            )
            await product_repository.create_product(trial_product)

            await message.answer(
                f"✅ Пробная ссылка успешно сохранена в базу данных!\n\n"
                f"🏷 <b>Пробная (trial) подписка:</b>\n🔗 <code>{trial_link}</code>"
            )

    except Exception as e:
        logger.error(f"Error saving trial subscription link: {e}")
        await message.answer("❌ Произошла ошибка при сохранении пробной ссылки.")
        return

    # Move to next state to get monthly link
    await state.set_state(SubscriptionLinkStates.waiting_for_monthly_link)
    await message.answer(
        "🔗 <b>Введите ссылку для месячной (monthly) подписки:</b>\n\n"
        "Для прекращения введите команду /cancel"
    )


async def process_monthly_link(message: Message, state: FSMContext) -> None:
    """Process the monthly link sent by admin and save it immediately."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте ссылку текстом.")
        return

    monthly_link = message.text.strip()

    # Save the monthly link to database immediately
    try:
        async with async_session_maker() as session:
            product_repository = ProductRepository(session)

            # Deactivate existing monthly product first (to update it)
            existing_products = await product_repository.get_all_products()
            for product in existing_products:
                if product.subscription_type == "monthly":
                    await product_repository.update_product(product.id, is_active=False)

            # Create new monthly product
            from src.models.product import Product

            monthly_product = Product(
                subscription_type=SubscriptionType.MONTHLY,
                price=299.0,  # Default price
                duration_days=30,  # Monthly
                device_limit=1,
                is_active=True,
                happ_link=monthly_link,
            )
            await product_repository.create_product(monthly_product)

            await message.answer(
                f"✅ Месячная ссылка успешно сохранена в базу данных!\n\n"
                f"🏷 <b>Месячная (monthly) подписка:</b>\n🔗 <code>{monthly_link}</code>"
            )

    except Exception as e:
        logger.error(f"Error saving monthly subscription link: {e}")
        await message.answer("❌ Произошла ошибка при сохранении месячной ссылки.")
        return

    # Move to next state to get quarterly link
    await state.set_state(SubscriptionLinkStates.waiting_for_quarterly_link)
    await message.answer(
        "🔗 <b>Введите ссылку для квартальной (quarterly) подписки:</b>\n\n"
        "Для прекращения введите команду /cancel"
    )


async def process_quarterly_link(message: Message, state: FSMContext) -> None:
    """Process the quarterly link sent by admin and save it immediately."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте ссылку текстом.")
        return

    quarterly_link = message.text.strip()

    # Save the quarterly link to database immediately
    try:
        async with async_session_maker() as session:
            product_repository = ProductRepository(session)

            # Deactivate existing quarterly product first (to update it)
            existing_products = await product_repository.get_all_products()
            for product in existing_products:
                if product.subscription_type == "quarterly":
                    await product_repository.update_product(product.id, is_active=False)

            # Create new quarterly product
            from src.models.product import Product

            quarterly_product = Product(
                subscription_type=SubscriptionType.QUARTERLY,
                price=799.0,  # Default price
                duration_days=90,  # Quarterly (3 months)
                device_limit=1,
                is_active=True,
                happ_link=quarterly_link,
            )
            await product_repository.create_product(quarterly_product)

            await message.answer(
                f"✅ Квартальная ссылка успешно сохранена в базу данных!\n\n"
                f"🏷 <b>Квартальная (quarterly) подписка:</b>\n🔗 <code>{quarterly_link}</code>"
            )

    except Exception as e:
        logger.error(f"Error saving quarterly subscription link: {e}")
        await message.answer("❌ Произошла ошибка при сохранении квартальной ссылки.")
        return

    # Move to next state to get yearly link
    await state.set_state(SubscriptionLinkStates.waiting_for_yearly_link)
    await message.answer(
        "🔗 <b>Введите ссылку для годовой (yearly) подписки:</b>\n\n"
        "Для прекращения введите команду /cancel"
    )


async def process_yearly_link(message: Message, state: FSMContext) -> None:
    """Process the yearly link sent by admin and save it immediately."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте ссылку текстом.")
        return

    yearly_link = message.text.strip()

    # Save the yearly link to database immediately
    try:
        async with async_session_maker() as session:
            product_repository = ProductRepository(session)

            # Deactivate existing yearly product first (to update it)
            existing_products = await product_repository.get_all_products()
            for product in existing_products:
                if product.subscription_type == "yearly":
                    await product_repository.update_product(product.id, is_active=False)

            # Create new yearly product
            from src.models.product import Product

            yearly_product = Product(
                subscription_type=SubscriptionType.YEARLY,
                price=2499.0,  # Default price
                duration_days=365,  # Yearly
                device_limit=5,
                is_active=True,
                happ_link=yearly_link,
            )
            await product_repository.create_product(yearly_product)

            await message.answer(
                f"✅ Годовая ссылка успешно сохранена в базу данных!\n\n"
                f"🏷 <b>Годовая (yearly) подписка:</b>\n🔗 <code>{yearly_link}</code>"
            )

            await message.answer("🎉 Все четыре ссылки успешно сохранены в базу данных!")

    except Exception as e:
        logger.error(f"Error saving yearly subscription link: {e}")
        await message.answer("❌ Произошла ошибка при сохранении годовой ссылки.")

    # Clear state
    await state.clear()


async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Cancel the subscription link collection process."""
    # Check if user is admin
    if not message.from_user:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    user_id = str(message.from_user.id)
    if user_id not in settings.admin_id_list:
        logger.warning(f"Non-admin user {user_id} tried to use cancel command")
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    current_state = await state.get_state()
    if current_state is None:
        await message.answer("❌ Нет активного процесса для отмены.")
        return

    # Check if we're in one of the subscription link states
    if current_state in [
        SubscriptionLinkStates.waiting_for_trial_link,
        SubscriptionLinkStates.waiting_for_monthly_link,
        SubscriptionLinkStates.waiting_for_quarterly_link,
        SubscriptionLinkStates.waiting_for_yearly_link,
    ]:
        await state.clear()
        await message.answer("❌ Процесс ввода ссылок отменен.")
    elif current_state in [
        BroadcastStates.waiting_for_all_message,
        BroadcastStates.waiting_for_paid_message,
    ]:
        await state.clear()
        await message.answer("❌ Процесс рассылки отменен.")
    else:
        await message.answer("❌ Команда /cancel не применима в текущем состоянии.")


async def cmd_all_message(message: Message, state: FSMContext) -> None:
    """Admin command to send message to all users."""
    if not message.from_user:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    user_id = str(message.from_user.id)
    if user_id not in settings.admin_id_list:
        logger.warning(f"Non-admin user {user_id} tried to access broadcast command")
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    await state.set_state(BroadcastStates.waiting_for_all_message)
    await message.answer(
        "📢 <b>Рассылка всем пользователям</b>\n\n"
        "Введите сообщение, которое будет отправлено всем пользователям:\n"
        "Для отмены введите /cancel"
    )
    logger.info(f"Admin {user_id} started broadcast to all users")


async def cmd_paid_message(message: Message, state: FSMContext) -> None:
    """Admin command to send message to users with paid subscription."""
    if not message.from_user:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    user_id = str(message.from_user.id)
    if user_id not in settings.admin_id_list:
        logger.warning(f"Non-admin user {user_id} tried to access paid broadcast command")
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    await state.set_state(BroadcastStates.waiting_for_paid_message)
    await message.answer(
        "📢 <b>Рассылка пользователям с платной подпиской</b>\n\n"
        "Введите сообщение, которое будет отправлено пользователям с активной платной подпиской:\n"
        "Для отмены введите /cancel"
    )
    logger.info(f"Admin {user_id} started broadcast to paid users")


async def process_all_message(message: Message, state: FSMContext) -> None:
    """Process and send broadcast message to all users."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте сообщение текстом.")
        return

    if not message.bot:
        await message.answer("❌ Ошибка доступа к боту.")
        return

    broadcast_text = message.text.strip()
    sent_count = 0
    error_count = 0

    try:
        async with async_session_maker() as session:
            user_repository = UserRepository(session)
            users = await user_repository.get_all_users()

            await message.answer(f"📤 Начинаю рассылку {len(users)} пользователям...")

            for user in users:
                try:
                    await message.bot.send_message(
                        chat_id=user.telegram_id, text=broadcast_text, parse_mode="HTML"
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Failed to send message to user {user.telegram_id}: {e}")
                    error_count += 1

        await message.answer(
            f"✅ Рассылка завершена!\n📤 Отправлено: {sent_count}\n❌ Ошибок: {error_count}"
        )

    except Exception as e:
        logger.error(f"Error during broadcast: {e}")
        await message.answer(f"❌ Произошла ошибка при рассылке: {e}")
    finally:
        await state.clear()


async def process_paid_message(message: Message, state: FSMContext) -> None:
    """Process and send broadcast message to users with paid subscription."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте сообщение текстом.")
        return

    if not message.bot:
        await message.answer("❌ Ошибка доступа к боту.")
        return

    broadcast_text = message.text.strip()
    sent_count = 0
    error_count = 0

    try:
        async with async_session_maker() as session:
            user_repository = UserRepository(session)
            users = await user_repository.get_users_with_active_subscription()

            await message.answer(
                f"📤 Начинаю рассылку {len(users)} пользователям с платной подпиской..."
            )

            for user in users:
                try:
                    await message.bot.send_message(
                        chat_id=user.telegram_id, text=broadcast_text, parse_mode="HTML"
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Failed to send message to user {user.telegram_id}: {e}")
                    error_count += 1

        await message.answer(
            f"✅ Рассылка завершена!\n📤 Отправлено: {sent_count}\n❌ Ошибок: {error_count}"
        )

    except Exception as e:
        logger.error(f"Error during paid broadcast: {e}")
        await message.answer(f"❌ Произошла ошибка при рассылке: {e}")
    finally:
        await state.clear()


def register_admin_handlers(dp: Dispatcher) -> None:
    """Register admin command handlers."""
    # Command to start the process
    dp.message.register(cmd_send_subscription_links, Command(Commands.SEND_SUBSCRIPTION_LINKS))

    # Broadcast commands (only for admins)
    dp.message.register(cmd_all_message, Command(Commands.ALL_MESSAGE))
    dp.message.register(cmd_paid_message, Command(Commands.PAID_MESSAGE))

    # Cancel command for all states (only for admins)
    dp.message.register(cmd_cancel, Command("cancel"))

    # Handlers for subscription link states
    dp.message.register(process_trial_link, SubscriptionLinkStates.waiting_for_trial_link)
    dp.message.register(process_monthly_link, SubscriptionLinkStates.waiting_for_monthly_link)
    dp.message.register(process_quarterly_link, SubscriptionLinkStates.waiting_for_quarterly_link)
    dp.message.register(process_yearly_link, SubscriptionLinkStates.waiting_for_yearly_link)

    # Handlers for broadcast states
    dp.message.register(process_all_message, BroadcastStates.waiting_for_all_message)
    dp.message.register(process_paid_message, BroadcastStates.waiting_for_paid_message)

    logger.info("Admin handlers registered")

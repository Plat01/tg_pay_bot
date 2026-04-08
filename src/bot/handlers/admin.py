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
from src.infrastructure.database.repositories import ProductRepository
from src.models.product import SubscriptionType

logger = logging.getLogger(__name__)


class SubscriptionLinkStates(StatesGroup):
    """States for collecting subscription links from admin."""

    waiting_for_trial_link = State()
    waiting_for_monthly_link = State()
    waiting_for_yearly_link = State()


async def cmd_send_subscription_links(message: Message, state: FSMContext) -> None:
    """Admin command to collect subscription links.

    Only accessible to admin users defined in settings.admin_ids.
    Prompts admin to send trial, monthly, and yearly links separately.
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

            await message.answer("🎉 Все три ссылки успешно сохранены в базу данных!")

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
        SubscriptionLinkStates.waiting_for_yearly_link,
    ]:
        await state.clear()
        await message.answer("❌ Процесс ввода ссылок отменен.")
    else:
        await message.answer("❌ Команда /cancel не применима в текущем состоянии.")


def register_admin_handlers(dp: Dispatcher) -> None:
    """Register admin command handlers."""
    # Command to start the process
    dp.message.register(cmd_send_subscription_links, Command(Commands.SEND_SUBSCRIPTION_LINKS))

    # Cancel command for all states (only for admins)
    dp.message.register(cmd_cancel, Command("cancel"))

    # Handlers for each state
    dp.message.register(process_trial_link, SubscriptionLinkStates.waiting_for_trial_link)
    dp.message.register(process_monthly_link, SubscriptionLinkStates.waiting_for_monthly_link)
    dp.message.register(process_yearly_link, SubscriptionLinkStates.waiting_for_yearly_link)

    logger.info("Admin handlers registered")

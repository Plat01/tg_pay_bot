"""Admin command handlers for administrative functions."""

import asyncio
import logging

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.bot.constants import CallbackData, Commands
from src.config import settings
from src.infrastructure.database import async_session_maker
from src.infrastructure.database.repositories import (
    PaymentRepository,
    ProductRepository,
    UserRepository,
)
from src.models.product import Product, SubscriptionType
from src.models.subscription import Subscription
from src.services.tariff import TariffService

logger = logging.getLogger(__name__)


class SubscriptionLinkStates(StatesGroup):
    """States for collecting subscription links from admin."""

    waiting_for_trial_link = State()
    waiting_for_monthly_link = State()
    waiting_for_quarterly_link = State()
    waiting_for_yearly_link = State()


class PriceEditStates(StatesGroup):
    """States for editing prices."""

    waiting_for_monthly_price = State()
    waiting_for_quarterly_price = State()
    waiting_for_yearly_price = State()


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
            tariff_service = TariffService(session)

            # Get price from tariff service (cached or default)
            tariff_data = await tariff_service.get_tariff_data("monthly")
            price = tariff_data["price"] if tariff_data else 199.0

            # Deactivate existing monthly product first (to update it)
            existing_products = await product_repository.get_all_products()
            for product in existing_products:
                if product.subscription_type == "monthly":
                    await product_repository.update_product(product.id, is_active=False)

            # Create new monthly product
            monthly_product = Product(
                subscription_type=SubscriptionType.MONTHLY,
                price=price,
                duration_days=30,
                device_limit=1,
                is_active=True,
                happ_link=monthly_link,
            )
            await product_repository.create_product(monthly_product)

            await message.answer(
                f"✅ Месячная ссылка успешно сохранена в базу данных!\n\n"
                f"🏷 <b>Месячная (monthly) подписка:</b>\n🔗 <code>{monthly_link}</code>\n"
                f"💰 Цена: {int(price)} ₽"
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
            tariff_service = TariffService(session)

            # Get price from tariff service (cached or default)
            tariff_data = await tariff_service.get_tariff_data("quarterly")
            price = tariff_data["price"] if tariff_data else 499.0

            # Deactivate existing quarterly product first (to update it)
            existing_products = await product_repository.get_all_products()
            for product in existing_products:
                if product.subscription_type == "quarterly":
                    await product_repository.update_product(product.id, is_active=False)

            # Create new quarterly product
            quarterly_product = Product(
                subscription_type=SubscriptionType.QUARTERLY,
                price=price,
                duration_days=90,
                device_limit=1,
                is_active=True,
                happ_link=quarterly_link,
            )
            await product_repository.create_product(quarterly_product)

            await message.answer(
                f"✅ Квартальная ссылка успешно сохранена в базу данных!\n\n"
                f"🏷 <b>Квартальная (quarterly) подписка:</b>\n🔗 <code>{quarterly_link}</code>\n"
                f"💰 Цена: {int(price)} ₽"
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
            tariff_service = TariffService(session)

            # Get price from tariff service (cached or default)
            tariff_data = await tariff_service.get_tariff_data("yearly")
            price = tariff_data["price"] if tariff_data else 1999.0

            # Deactivate existing yearly product first (to update it)
            existing_products = await product_repository.get_all_products()
            for product in existing_products:
                if product.subscription_type == "yearly":
                    await product_repository.update_product(product.id, is_active=False)

            # Create new yearly product
            yearly_product = Product(
                subscription_type=SubscriptionType.YEARLY,
                price=price,
                duration_days=365,
                device_limit=5,
                is_active=True,
                happ_link=yearly_link,
            )
            await product_repository.create_product(yearly_product)

            await message.answer(
                f"✅ Годовая ссылка успешно сохранена в базу данных!\n\n"
                f"🏷 <b>Годовая (yearly) подписка:</b>\n🔗 <code>{yearly_link}</code>\n"
                f"💰 Цена: {int(price)} ₽"
            )

            await message.answer("🎉 Все четыре ссылки успешно сохранены в базу данных!")

    except Exception as e:
        logger.error(f"Error saving yearly subscription link: {e}")
        await message.answer("❌ Произошла ошибка при сохранении годовой ссылки.")
        return

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


async def cmd_subscriptions(message: Message) -> None:
    """Admin command to show all users with active subscriptions."""
    if not message.from_user:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    user_id = str(message.from_user.id)
    if user_id not in settings.admin_id_list:
        logger.warning(f"Non-admin user {user_id} tried to access subscriptions command")
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    try:
        async with async_session_maker() as session:
            from zoneinfo import ZoneInfo

            from src.infrastructure.database.repositories import SubscriptionRepository

            subscription_repository = SubscriptionRepository(session)
            subscriptions = (
                await subscription_repository.get_all_active_subscriptions_with_details()
            )

            if not subscriptions:
                await message.answer("📋 Нет активных подписок.")
                return

            msk_tz = ZoneInfo("Europe/Moscow")

            # Group subscriptions by user
            user_subscriptions: dict[str, list[Subscription]] = {}
            for sub in subscriptions:
                if sub.user:
                    telegram_id = sub.user.telegram_id
                    if telegram_id not in user_subscriptions:
                        user_subscriptions[telegram_id] = []
                    user_subscriptions[telegram_id].append(sub)

            # Build message
            lines = [f"📋 <b>Активные подписки ({len(subscriptions)} шт):</b>\n"]

            for telegram_id, subs in user_subscriptions.items():
                user = subs[0].user
                username = f"@{user.username}" if user.username else "Без username"
                user_link = f'<a href="tg://user?id={telegram_id}">{username}</a>'

                lines.append(f"\n👤 {user_link} (ID: {telegram_id})")

                for sub in subs:
                    if sub.product:
                        sub_type = sub.product.subscription_type
                        end_date_msk = sub.end_date.astimezone(msk_tz)
                        end_date_str = end_date_msk.strftime("%d.%m.%Y %H:%M МСК")
                        lines.append(f"  • {sub_type}: до {end_date_str}")

            # Send in chunks if message is too long
            full_message = "\n".join(lines)
            if len(full_message) <= 4096:
                await message.answer(full_message, parse_mode="HTML")
            else:
                # Split into chunks
                chunks = []
                current_chunk = lines[0] + "\n"  # Header
                for line in lines[1:]:
                    if len(current_chunk) + len(line) + 1 > 4096:
                        chunks.append(current_chunk)
                        current_chunk = line
                    else:
                        current_chunk += "\n" + line
                if current_chunk:
                    chunks.append(current_chunk)

                for chunk in chunks:
                    await message.answer(chunk, parse_mode="HTML")
                    await asyncio.sleep(0.1)  # Avoid rate limiting

            logger.info(f"Admin {user_id} viewed all subscriptions")

    except Exception as e:
        logger.error(f"Error showing subscriptions: {e}")
        await message.answer(f"❌ Произошла ошибка при получении подписок: {e}")


async def cmd_prices(message: Message) -> None:
    """Admin command to show current prices with edit buttons."""
    if not message.from_user:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    user_id = str(message.from_user.id)
    if user_id not in settings.admin_id_list:
        logger.warning(f"Non-admin user {user_id} tried to access prices command")
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    try:
        async with async_session_maker() as session:
            tariff_service = TariffService(session)
            await tariff_service.refresh_cache()
            tariffs = await tariff_service.get_all_tariffs()

        monthly_price = int(tariffs.get("monthly", {}).get("price", 199))
        quarterly_price = int(tariffs.get("quarterly", {}).get("price", 499))
        yearly_price = int(tariffs.get("yearly", {}).get("price", 1999))

        text = (
            "💰 <b>Текущие цены подписок:</b>\n\n"
            f"• 1 месяц: {monthly_price} ₽\n"
            f"• 3 месяца: {quarterly_price} ₽\n"
            f"• 12 месяцев: {yearly_price} ₽\n\n"
            "Нажмите кнопку для редактирования цены:"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"✏️ Изменить 1 месяц ({monthly_price} ₽)",
                        callback_data="edit_price:monthly",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"✏️ Изменить 3 месяца ({quarterly_price} ₽)",
                        callback_data="edit_price:quarterly",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"✏️ Изменить 12 месяцев ({yearly_price} ₽)",
                        callback_data="edit_price:yearly",
                    )
                ],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
            ]
        )

        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
        logger.info(f"Admin {user_id} viewed current prices")

    except Exception as e:
        logger.error(f"Error showing prices: {e}")
        await message.answer("❌ Произошла ошибка при получении цен.")


async def cmd_user_payments(message: Message) -> None:
    """Admin command to show user payments by telegram ID.

    Usage: /payments <telegram_id>
    """
    if not message.from_user:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    admin_id = str(message.from_user.id)
    if admin_id not in settings.admin_id_list:
        logger.warning(f"Non-admin user {admin_id} tried to access payments command")
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    if not message.text:
        await message.answer(
            "❌ Укажите Telegram ID пользователя.\n\nИспользование: /payments <telegram_id>"
        )
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "❌ Укажите Telegram ID пользователя.\n\nИспользование: /payments <telegram_id>"
        )
        return

    telegram_id = parts[1].strip()

    try:
        async with async_session_maker() as session:
            user_repository = UserRepository(session)
            payment_repository = PaymentRepository(session)

            user = await user_repository.get_by_telegram_id(telegram_id)
            if not user:
                await message.answer(f"❌ Пользователь с Telegram ID {telegram_id} не найден.")
                return

            payments = await payment_repository.get_user_payments(user.id)

            if not payments:
                await message.answer(
                    f"📋 У пользователя {telegram_id} нет платежей.", parse_mode="HTML"
                )
                return

            from zoneinfo import ZoneInfo

            msk_tz = ZoneInfo("Europe/Moscow")

            username = f"@{user.username}" if user.username else "Без username"
            lines = [f"💳 <b>Платежи пользователя {username} (ID: {telegram_id})</b>\n"]
            lines.append(f"📊 Всего платежей: {len(payments)}\n")

            status_emoji = {
                "completed": "✅",
                "paid": "✅",
                "pending": "⏳",
                "failed": "❌",
                "cancelled": "🚫",
                "expired": "⏰",
            }

            for payment in payments:
                status = (
                    payment.status.value
                    if hasattr(payment.status, "value")
                    else str(payment.status)
                )
                emoji = status_emoji.get(status, "❓")
                created_msk = payment.created_at.astimezone(msk_tz)
                created_str = created_msk.strftime("%d.%m.%Y %H:%M МСК")

                lines.append(f"\n{emoji} <b>{payment.amount:.2f} {payment.currency}</b>")
                lines.append(f"  Статус: {status}")
                lines.append(f"  Провайдер: {payment.payment_provider or 'N/A'}")
                lines.append(f"  Создан: {created_str}")
                if payment.completed_at:
                    completed_msk = payment.completed_at.astimezone(msk_tz)
                    completed_str = completed_msk.strftime("%d.%m.%Y %H:%M МСК")
                    lines.append(f"  Завершен: {completed_str}")

            full_message = "\n".join(lines)
            if len(full_message) <= 4096:
                await message.answer(full_message, parse_mode="HTML")
            else:
                chunks = []
                current_chunk = lines[0] + "\n"
                for line in lines[1:]:
                    if len(current_chunk) + len(line) + 1 > 4096:
                        chunks.append(current_chunk)
                        current_chunk = line
                    else:
                        current_chunk += "\n" + line
                if current_chunk:
                    chunks.append(current_chunk)

                for chunk in chunks:
                    await message.answer(chunk, parse_mode="HTML")
                    await asyncio.sleep(0.1)

            logger.info(f"Admin {admin_id} viewed payments for user {telegram_id}")

    except Exception as e:
        logger.error(f"Error showing user payments: {e}")
        await message.answer(f"❌ Произошла ошибка при получении платежей: {e}")


async def handle_edit_price(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle edit price button click."""
    if not callback.from_user:
        await callback.answer("❌ Не удалось определить пользователя.")
        return

    user_id = str(callback.from_user.id)
    if user_id not in settings.admin_id_list:
        await callback.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    try:
        tariff_type = callback.data.split(":")[1]
    except (ValueError, IndexError):
        await callback.answer("❌ Неверный формат.")
        return

    if tariff_type not in ["monthly", "quarterly", "yearly"]:
        await callback.answer("❌ Неверный тип тарифа.")
        return

    # Set appropriate state
    state_map = {
        "monthly": PriceEditStates.waiting_for_monthly_price,
        "quarterly": PriceEditStates.waiting_for_quarterly_price,
        "yearly": PriceEditStates.waiting_for_yearly_price,
    }

    await state.set_state(state_map[tariff_type])
    await state.update_data(tariff_type=tariff_type)

    tariff_names = {
        "monthly": "1 месяц",
        "quarterly": "3 месяца",
        "yearly": "12 месяцев",
    }

    await callback.message.edit_text(
        f"✏️ <b>Изменение цены для тарифа: {tariff_names[tariff_type]}</b>\n\n"
        "Введите новую цену (в рублях):\n"
        "Для отмены введите /cancel",
        parse_mode="HTML",
    )
    await callback.answer()


async def process_price_edit(message: Message, state: FSMContext) -> None:
    """Process new price input from admin."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте цену текстом.")
        return

    if not message.from_user:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    user_id = str(message.from_user.id)
    if user_id not in settings.admin_id_list:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    try:
        new_price = float(message.text.strip())
        if new_price < 0:
            await message.answer("❌ Цена должна быть положительным числом.")
            return
    except ValueError:
        await message.answer("❌ Неверный формат цены. Введите число (например: 299).")
        return

    data = await state.get_data()
    tariff_type = data.get("tariff_type")

    if not tariff_type:
        await message.answer("❌ Ошибка: тип тарифа не найден.")
        await state.clear()
        return

    try:
        async with async_session_maker() as session:
            product_repository = ProductRepository(session)
            tariff_service = TariffService(session)

            # Get current tariff data
            tariff_data = await tariff_service.get_tariff_data(tariff_type)
            old_price = tariff_data["price"] if tariff_data else 199.0

            # Get or create product
            product = await product_repository.get_product_by_subscription_type(tariff_type)

            if product:
                # Update existing product
                await product_repository.update_product(product.id, price=new_price)
            else:
                # Create new product if not exists
                duration_map = {"monthly": 30, "quarterly": 90, "yearly": 365}
                new_product = Product(
                    subscription_type=tariff_type,
                    price=new_price,
                    duration_days=duration_map[tariff_type],
                    device_limit=1,
                    is_active=True,
                    happ_link="",  # Will be set by /send_sub_links command
                )
                await product_repository.create_product(new_product)

            # Refresh cache
            await tariff_service.refresh_cache()

            tariff_names = {
                "monthly": "1 месяц",
                "quarterly": "3 месяца",
                "yearly": "12 месяцев",
            }

            await message.answer(
                f"✅ Цена для тарифа <b>{tariff_names[tariff_type]}</b> обновлена!\n\n"
                f"💰 Старая цена: {int(old_price)} ₽\n"
                f"💰 Новая цена: {int(new_price)} ₽\n\n"
                "Кэш обновлен. Пользователи увидят новую цену сразу.",
                parse_mode="HTML",
            )

            logger.info(
                f"Admin {user_id} updated price for {tariff_type}: {old_price} → {new_price}"
            )

    except Exception as e:
        logger.error(f"Error updating price: {e}")
        await message.answer("❌ Произошла ошибка при обновлении цены.")
        return

    await state.clear()


def register_admin_handlers(dp: Dispatcher) -> None:
    """Register admin command handlers."""
    dp.message.register(cmd_send_subscription_links, Command(Commands.SEND_SUBSCRIPTION_LINKS))
    dp.message.register(cmd_prices, Command(Commands.PRICES))
    dp.message.register(cmd_subscriptions, Command(Commands.SUBSCRIPTIONS))
    dp.message.register(cmd_user_payments, Command(Commands.USER_PAYMENTS))
    dp.message.register(cmd_all_message, Command(Commands.ALL_MESSAGE))
    dp.message.register(cmd_paid_message, Command(Commands.PAID_MESSAGE))
    dp.message.register(cmd_cancel, Command("cancel"))

    # Handlers for subscription link states
    dp.message.register(process_trial_link, SubscriptionLinkStates.waiting_for_trial_link)
    dp.message.register(process_monthly_link, SubscriptionLinkStates.waiting_for_monthly_link)
    dp.message.register(process_quarterly_link, SubscriptionLinkStates.waiting_for_quarterly_link)
    dp.message.register(process_yearly_link, SubscriptionLinkStates.waiting_for_yearly_link)

    # Handlers for price edit states
    dp.message.register(process_price_edit, PriceEditStates.waiting_for_monthly_price)
    dp.message.register(process_price_edit, PriceEditStates.waiting_for_quarterly_price)
    dp.message.register(process_price_edit, PriceEditStates.waiting_for_yearly_price)

    # Callback handler for edit price buttons
    dp.callback_query.register(handle_edit_price, F.data.startswith("edit_price:"))

    # Handlers for broadcast states
    dp.message.register(process_all_message, BroadcastStates.waiting_for_all_message)
    dp.message.register(process_paid_message, BroadcastStates.waiting_for_paid_message)

    logger.info("Admin handlers registered")

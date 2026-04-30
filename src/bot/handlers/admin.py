"""Admin command handlers for administrative functions."""

import asyncio
import logging
from zoneinfo import ZoneInfo

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
    UserRepository,
    SubscriptionRepository,
)
from src.models.subscription import Subscription
from src.services.tariff import TariffService, DEFAULT_PRICES

logger = logging.getLogger(__name__)

MSK_TZ = ZoneInfo("Europe/Moscow")


class BroadcastStates(StatesGroup):
    """States for broadcast message collection."""

    waiting_for_all_message = State()
    waiting_for_paid_message = State()


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
            subscription_repository = SubscriptionRepository(session)
            subscriptions = await subscription_repository.get_all_active_subscriptions_with_details()

            if not subscriptions:
                await message.answer("📋 Нет активных подписок.")
                return

            user_subscriptions: dict[str, list[Subscription]] = {}
            for sub in subscriptions:
                if sub.user:
                    telegram_id = sub.user.telegram_id
                    if telegram_id not in user_subscriptions:
                        user_subscriptions[telegram_id] = []
                    user_subscriptions[telegram_id].append(sub)

            lines = [f"📋 <b>Активные подписки ({len(subscriptions)} шт):</b>\n"]

            for telegram_id, subs in user_subscriptions.items():
                user = subs[0].user
                username = f"@{user.username}" if user.username else "Без username"
                user_link = f'<a href="tg://user?id={telegram_id}">{username}</a>'

                lines.append(f"\n👤 {user_link} (ID: {telegram_id})")

                for sub in subs:
                    sub_type = sub.subscription_type or "unknown"
                    end_date_msk = sub.end_date.astimezone(MSK_TZ)
                    end_date_str = end_date_msk.strftime("%d.%m.%Y %H:%M МСК")
                    lines.append(f"  • {sub_type}: до {end_date_str}")

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

            logger.info(f"Admin {user_id} viewed all subscriptions")

    except Exception as e:
        logger.error(f"Error showing subscriptions: {e}")
        await message.answer(f"❌ Произошла ошибка при получении подписок: {e}")


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
                created_msk = payment.created_at.astimezone(MSK_TZ)
                created_str = created_msk.strftime("%d.%m.%Y %H:%M МСК")

                lines.append(f"\n{emoji} <b>{payment.amount:.2f} {payment.currency}</b>")
                lines.append(f"  Статус: {status}")
                lines.append(f"  Провайдер: {payment.payment_provider or 'N/A'}")
                lines.append(f"  Создан: {created_str}")
                if payment.completed_at:
                    completed_msk = payment.completed_at.astimezone(MSK_TZ)
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


async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Cancel the current broadcast process."""
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

    if current_state in [
        BroadcastStates.waiting_for_all_message,
        BroadcastStates.waiting_for_paid_message,
    ]:
        await state.clear()
        await message.answer("❌ Процесс рассылки отменен.")
    else:
        await message.answer("❌ Команда /cancel не применима в текущем состоянии.")


def register_admin_handlers(dp: Dispatcher) -> None:
    """Register admin command handlers."""
    dp.message.register(cmd_subscriptions, Command(Commands.SUBSCRIPTIONS))
    dp.message.register(cmd_user_payments, Command(Commands.USER_PAYMENTS))
    dp.message.register(cmd_all_message, Command(Commands.ALL_MESSAGE))
    dp.message.register(cmd_paid_message, Command(Commands.PAID_MESSAGE))
    dp.message.register(cmd_cancel, Command("cancel"))

    dp.message.register(process_all_message, BroadcastStates.waiting_for_all_message)
    dp.message.register(process_paid_message, BroadcastStates.waiting_for_paid_message)

    logger.info("Admin handlers registered")
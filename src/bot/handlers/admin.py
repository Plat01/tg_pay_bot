"""Admin command handlers for administrative functions."""

import asyncio
import logging
from zoneinfo import ZoneInfo

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from src.bot.constants import Commands
from src.config import settings
from src.infrastructure.database import async_session_maker
from src.infrastructure.database.repositories import (
    PaymentRepository,
    SubscriptionRepository,
    UserRepository,
)
from src.models.subscription import Subscription
from src.services.subscription import TARIFF_DURATION_DAYS, SubscriptionService
from src.services.user import UserService

logger = logging.getLogger(__name__)

MSK_TZ = ZoneInfo("Europe/Moscow")


class BroadcastStates(StatesGroup):
    """States for broadcast message collection."""

    waiting_for_all_message = State()
    waiting_for_paid_message = State()


class AddBalanceStates(StatesGroup):
    """States for balance top-up process."""

    waiting_for_telegram_id = State()
    waiting_for_amount = State()
    waiting_for_notification_message = State()
    waiting_for_confirmation = State()


class GrantSubscriptionStates(StatesGroup):
    """States for granting subscription process."""

    waiting_for_telegram_id = State()
    waiting_for_subscription_type = State()
    waiting_for_confirmation = State()


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
            subscriptions = (
                await subscription_repository.get_all_active_subscriptions_with_details()
            )

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


async def cmd_add_balance(message: Message, state: FSMContext) -> None:
    """Admin command to add balance to user by telegram ID.

    Usage: /add_balance [telegram_id] [amount]
    If arguments provided, executes immediately.
    Otherwise starts interactive process.
    """
    if not message.from_user:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    admin_id = str(message.from_user.id)
    if admin_id not in settings.admin_id_list:
        logger.warning(f"Non-admin user {admin_id} tried to access add_balance command")
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    parts = message.text.split() if message.text else []

    if len(parts) >= 3:
        telegram_id = parts[1].strip()
        try:
            amount = float(parts[2].strip())
            if amount <= 0:
                await message.answer("❌ Сумма должна быть положительным числом.")
                return
        except ValueError:
            await message.answer("❌ Неверный формат суммы. Укажите число.")
            return

        await _execute_add_balance(message, telegram_id, amount)
    else:
        await state.set_state(AddBalanceStates.waiting_for_telegram_id)
        await message.answer(
            "💰 <b>Начисление баланса пользователю</b>\n\n"
            "Введите Telegram ID пользователя:\n"
            "Для отмены введите /cancel"
        )
        logger.info(f"Admin {admin_id} started add_balance process")


async def process_add_balance_telegram_id(message: Message, state: FSMContext) -> None:
    """Process telegram ID input for balance top-up."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте текст.")
        return

    telegram_id = message.text.strip()

    try:
        async with async_session_maker() as session:
            user_repository = UserRepository(session)
            payment_repository = PaymentRepository(session)

            user = await user_repository.get_by_telegram_id(telegram_id)
            if not user:
                await message.answer(
                    f"❌ Пользователь с Telegram ID {telegram_id} не найден.\nПопробуйте снова:"
                )
                return

            # Получаем последние пополнения (completed/paid)
            from src.models.payment import PaymentStatus

            payments = await payment_repository.get_user_payments(
                user.id, status=PaymentStatus.COMPLETED, limit=50
            )

            # Формируем информацию о пользователе
            username = f"@{user.username}" if user.username else "Без username"
            info_lines = [
                f"👤 <b>Пользователь найден:</b> {username}",
                f"🆔 Telegram ID: {telegram_id}",
                f"💰 <b>Баланс:</b> {user.balance:.2f} RUB",
            ]

            # Добавляем информацию о пополнениях
            if payments:
                info_lines.append(f"\n📊 <b>Последние пополнения ({len(payments)}):</b>")
                for payment in payments:
                    created_msk = payment.created_at.astimezone(MSK_TZ)
                    created_str = created_msk.strftime("%d.%m.%Y %H:%M")
                    info_lines.append(f"  • {payment.amount:.2f} RUB — {created_str}")
            else:
                info_lines.append("\n📊 <b>Пополнений нет</b>")

            info_lines.append("\n\nВведите сумму для начисления (в рублях):")

            await state.update_data(
                telegram_id=telegram_id,
                user_display=f"@{user.username}" if user.username else telegram_id,
            )
            await state.set_state(AddBalanceStates.waiting_for_amount)
            await message.answer("\n".join(info_lines), parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error finding user for add_balance: {e}")
        await message.answer(f"❌ Ошибка при поиске пользователя: {e}")


async def process_add_balance_amount(message: Message, state: FSMContext) -> None:
    """Process amount input for balance top-up."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте текст.")
        return

    try:
        amount = float(message.text.strip())
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительным числом. Попробуйте снова:")
            return
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Введите число:")
        return

    await state.update_data(amount=amount)

    # Шаблон сообщения для пользователя
    default_notification = (
        f"💰 <b>Ваш баланс пополнен!</b>\n\n💵 Сумма: {amount:.2f} RUB\n\nСпасибо за доверие!"
    )

    await state.update_data(notification_message=default_notification)
    await state.set_state(AddBalanceStates.waiting_for_notification_message)

    await message.answer(
        f"📝 <b>Сообщение для пользователя</b>\n\n"
        f"Пользователь получит следующее сообщение после начисления.\n"
        f"Вы можете скопировать и отредактировать его, или отправить как есть:\n\n"
        f"<code>{default_notification}</code>\n\n"
        f"Отправьте сообщение или введите 'да' чтобы использовать шаблон выше:",
        parse_mode="HTML",
    )


async def process_add_balance_notification_message(message: Message, state: FSMContext) -> None:
    """Process notification message input for balance top-up."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте текст.")
        return

    data = await state.get_data()
    response = message.text.strip().lower()

    # Если админ согласен с шаблоном - используем сохраненный
    if response in ("да", "yes", "y", "д", "+", "ok", "ок"):
        notification_message = data.get("notification_message", "")
    else:
        # Админ отправил свое сообщение
        notification_message = message.text.strip()
        await state.update_data(notification_message=notification_message)

    await state.set_state(AddBalanceStates.waiting_for_confirmation)
    await message.answer(
        f"⚠️ <b>Подтверждение начисления</b>\n\n"
        f"👤 Пользователь: {data['user_display']}\n"
        f"🆔 Telegram ID: {data['telegram_id']}\n"
        f"💰 Сумма: {data['amount']:.2f} RUB\n\n"
        f"📝 Сообщение для пользователя:\n"
        f"<code>{notification_message}</code>\n\n"
        f"Подтвердите начисление (да/нет):",
        parse_mode="HTML",
    )


async def process_add_balance_confirmation(message: Message, state: FSMContext) -> None:
    """Process confirmation for balance top-up."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте текст.")
        return

    response = message.text.strip().lower()

    if response not in ("да", "yes", "y", "д", "+"):
        await state.clear()
        await message.answer("❌ Начисление отменено.")
        return

    data = await state.get_data()
    telegram_id = data["telegram_id"]
    amount = data["amount"]
    notification_message = data.get("notification_message", "")

    await state.clear()
    await _execute_add_balance(message, telegram_id, amount, notification_message)


async def _execute_add_balance(
    message: Message, telegram_id: str, amount: float, notification_message: str = ""
) -> None:
    """Execute balance top-up and send notification to user."""
    from decimal import Decimal

    if not message.bot:
        await message.answer("❌ Ошибка доступа к боту.")
        return

    try:
        async with async_session_maker() as session:
            user_service = UserService(session)
            user_repository = UserRepository(session)

            user = await user_repository.get_by_telegram_id(telegram_id)
            if not user:
                await message.answer(f"❌ Пользователь с Telegram ID {telegram_id} не найден.")
                return

            old_balance = user.balance
            new_balance = await user_service.update_balance(user, Decimal(str(amount)))

            # Отправка сообщения пользователю
            if notification_message:
                try:
                    await message.bot.send_message(
                        chat_id=telegram_id, text=notification_message, parse_mode="HTML"
                    )
                    notification_sent = True
                except Exception as e:
                    logger.error(f"Failed to send notification to user {telegram_id}: {e}")
                    notification_sent = False
            else:
                notification_sent = False

            username = f"@{user.username}" if user.username else telegram_id
            notification_status = (
                "✅ Отправлено"
                if notification_sent
                else "❌ Не отправлено (блок или без сообщения)"
            )

            await message.answer(
                f"✅ <b>Баланс успешно пополнен!</b>\n\n"
                f"👤 Пользователь: {username}\n"
                f"🆔 Telegram ID: {telegram_id}\n"
                f"💰 Начислено: {amount:.2f} RUB\n"
                f"📊 Было: {old_balance:.2f} RUB\n"
                f"📊 Стало: {new_balance.balance:.2f} RUB\n"
                f"📤 Уведомление: {notification_status}",
                parse_mode="HTML",
            )

            logger.info(
                f"Admin added {amount} RUB to user {telegram_id} "
                f"(balance: {old_balance} -> {new_balance.balance})"
            )

    except Exception as e:
        logger.error(f"Error adding balance: {e}")
        await message.answer(f"❌ Произошла ошибка при начислении баланса: {e}")


async def cmd_grant_subscription(message: Message, state: FSMContext) -> None:
    """Admin command to grant subscription to user by telegram ID.

    Usage: /grant_subscription [telegram_id] [subscription_type]
    If arguments provided, executes immediately.
    Otherwise starts interactive process.
    """
    if not message.from_user:
        await message.answer("❌ Не удалось определить пользователя.")
        return

    admin_id = str(message.from_user.id)
    if admin_id not in settings.admin_id_list:
        logger.warning(f"Non-admin user {admin_id} tried to access grant_subscription command")
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    parts = message.text.split() if message.text else []

    if len(parts) >= 3:
        telegram_id = parts[1].strip()
        subscription_type = parts[2].strip().lower()

        if subscription_type not in TARIFF_DURATION_DAYS:
            valid_types = ", ".join(TARIFF_DURATION_DAYS.keys())
            await message.answer(f"❌ Неверный тип подписки. Доступные типы: {valid_types}")
            return

        await _execute_grant_subscription(message, telegram_id, subscription_type)
    else:
        await state.set_state(GrantSubscriptionStates.waiting_for_telegram_id)
        await message.answer(
            "🎁 <b>Выдача подписки пользователю</b>\n\n"
            "Введите Telegram ID пользователя:\n"
            "Для отмены введите /cancel"
        )
        logger.info(f"Admin {admin_id} started grant_subscription process")


async def process_grant_subscription_telegram_id(message: Message, state: FSMContext) -> None:
    """Process telegram ID input for granting subscription."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте текст.")
        return

    telegram_id = message.text.strip()

    try:
        async with async_session_maker() as session:
            user_repository = UserRepository(session)
            subscription_repository = SubscriptionRepository(session)

            user = await user_repository.get_by_telegram_id(telegram_id)
            if not user:
                await message.answer(
                    f"❌ Пользователь с Telegram ID {telegram_id} не найден.\nПопробуйте снова:"
                )
                return

            subscriptions = await subscription_repository.get_active_subscriptions(user.id)

            username = f"@{user.username}" if user.username else "Без username"
            info_lines = [
                f"👤 <b>Пользователь найден:</b> {username}",
                f"🆔 Telegram ID: {telegram_id}",
            ]

            if subscriptions:
                info_lines.append(f"\n📋 <b>Активные подписки ({len(subscriptions)}):</b>")
                for sub in subscriptions:
                    sub_type = sub.subscription_type or "unknown"
                    end_date_msk = sub.end_date.astimezone(MSK_TZ)
                    end_date_str = end_date_msk.strftime("%d.%m.%Y %H:%M МСК")
                    info_lines.append(f"  • {sub_type}: до {end_date_str}")
            else:
                info_lines.append("\n📋 <b>Активных подписок нет</b>")

            info_lines.append("\n\n<b>Выберите тип подписки:</b>")
            for sub_type, days in TARIFF_DURATION_DAYS.items():
                info_lines.append(f"  /{sub_type} — {days} дней")

            await state.update_data(
                telegram_id=telegram_id,
                user_display=f"@{user.username}" if user.username else telegram_id,
            )
            await state.set_state(GrantSubscriptionStates.waiting_for_subscription_type)
            await message.answer("\n".join(info_lines), parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error finding user for grant_subscription: {e}")
        await message.answer(f"❌ Ошибка при поиске пользователя: {e}")


async def process_grant_subscription_type(message: Message, state: FSMContext) -> None:
    """Process subscription type selection for granting subscription."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте текст.")
        return

    text = message.text.strip().lower()
    sub_type = None

    for valid_type in TARIFF_DURATION_DAYS.keys():
        if text == f"/{valid_type}" or text == valid_type:
            sub_type = valid_type
            break

    if not sub_type:
        valid_types = ", ".join([f"/{t}" for t in TARIFF_DURATION_DAYS.keys()])
        await message.answer(f"❌ Неверный тип подписки. Выберите из списка:\n{valid_types}")
        return

    await state.update_data(subscription_type=sub_type)
    data = await state.get_data()

    duration_days = TARIFF_DURATION_DAYS[sub_type]

    await state.set_state(GrantSubscriptionStates.waiting_for_confirmation)
    await message.answer(
        f"⚠️ <b>Подтверждение выдачи подписки</b>\n\n"
        f"👤 Пользователь: {data['user_display']}\n"
        f"🆔 Telegram ID: {data['telegram_id']}\n"
        f"📦 Тип подписки: {sub_type}\n"
        f"⏱️ Длительность: {duration_days} дней\n\n"
        f"Подтвердите выдачу (да/нет):",
        parse_mode="HTML",
    )


async def process_grant_subscription_confirmation(message: Message, state: FSMContext) -> None:
    """Process confirmation for granting subscription."""
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте текст.")
        return

    response = message.text.strip().lower()

    if response not in ("да", "yes", "y", "д", "+"):
        await state.clear()
        await message.answer("❌ Выдача подписки отменена.")
        return

    data = await state.get_data()
    telegram_id = data["telegram_id"]
    subscription_type = data["subscription_type"]

    await state.clear()
    await _execute_grant_subscription(message, telegram_id, subscription_type)


async def _execute_grant_subscription(
    message: Message, telegram_id: str, subscription_type: str
) -> None:
    """Execute granting subscription and send notification to user."""
    if not message.bot:
        await message.answer("❌ Ошибка доступа к боту.")
        return

    try:
        async with async_session_maker() as session:
            user_repository = UserRepository(session)
            subscription_service = SubscriptionService(session)

            user = await user_repository.get_by_telegram_id(telegram_id)
            if not user:
                await message.answer(f"❌ Пользователь с Telegram ID {telegram_id} не найден.")
                return

            subscription = await subscription_service.create_subscription_by_type(
                user_id=user.id,
                subscription_type=subscription_type,
            )

            duration_days = TARIFF_DURATION_DAYS[subscription_type]
            end_date_msk = subscription.end_date.astimezone(MSK_TZ)
            end_date_str = end_date_msk.strftime("%d.%m.%Y %H:%M МСК")

            notification_message = (
                f"🎁 <b>Вам выдана подписка!</b>\n\n"
                f"📦 Тип: {subscription_type}\n"
                f"⏱️ Длительность: {duration_days} дней\n"
                f"📅 Действует до: {end_date_str}\n\n"
                f"Спасибо за доверие!"
            )

            notification_sent = False
            try:
                await message.bot.send_message(
                    chat_id=telegram_id, text=notification_message, parse_mode="HTML"
                )
                notification_sent = True
            except Exception as e:
                logger.error(f"Failed to send notification to user {telegram_id}: {e}")

            username = f"@{user.username}" if user.username else telegram_id
            notification_status = (
                "✅ Отправлено" if notification_sent else "❌ Не отправлено (блок)"
            )

            await message.answer(
                f"✅ <b>Подписка успешно выдана!</b>\n\n"
                f"👤 Пользователь: {username}\n"
                f"🆔 Telegram ID: {telegram_id}\n"
                f"📦 Тип подписки: {subscription_type}\n"
                f"⏱️ Длительность: {duration_days} дней\n"
                f"📅 Действует до: {end_date_str}\n"
                f"📤 Уведомление: {notification_status}",
                parse_mode="HTML",
            )

            logger.info(f"Admin granted {subscription_type} subscription to user {telegram_id}")

    except Exception as e:
        logger.error(f"Error granting subscription: {e}")
        await message.answer(f"❌ Произошла ошибка при выдаче подписки: {e}")


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
        AddBalanceStates.waiting_for_telegram_id,
        AddBalanceStates.waiting_for_amount,
        AddBalanceStates.waiting_for_notification_message,
        AddBalanceStates.waiting_for_confirmation,
        GrantSubscriptionStates.waiting_for_telegram_id,
        GrantSubscriptionStates.waiting_for_subscription_type,
        GrantSubscriptionStates.waiting_for_confirmation,
    ]:
        await state.clear()
        await message.answer("❌ Процесс отменен.")
    else:
        await message.answer("❌ Команда /cancel не применима в текущем состоянии.")


def register_admin_handlers(dp: Dispatcher) -> None:
    """Register admin command handlers."""
    dp.message.register(cmd_subscriptions, Command(Commands.SUBSCRIPTIONS))
    dp.message.register(cmd_user_payments, Command(Commands.USER_PAYMENTS))
    dp.message.register(cmd_all_message, Command(Commands.ALL_MESSAGE))
    dp.message.register(cmd_paid_message, Command(Commands.PAID_MESSAGE))
    dp.message.register(cmd_add_balance, Command(Commands.ADD_BALANCE))
    dp.message.register(cmd_grant_subscription, Command(Commands.GRANT_SUBSCRIPTION))
    dp.message.register(cmd_cancel, Command("cancel"))

    dp.message.register(process_all_message, BroadcastStates.waiting_for_all_message)
    dp.message.register(process_paid_message, BroadcastStates.waiting_for_paid_message)

    dp.message.register(process_add_balance_telegram_id, AddBalanceStates.waiting_for_telegram_id)
    dp.message.register(process_add_balance_amount, AddBalanceStates.waiting_for_amount)
    dp.message.register(
        process_add_balance_notification_message, AddBalanceStates.waiting_for_notification_message
    )
    dp.message.register(process_add_balance_confirmation, AddBalanceStates.waiting_for_confirmation)

    dp.message.register(
        process_grant_subscription_telegram_id, GrantSubscriptionStates.waiting_for_telegram_id
    )
    dp.message.register(
        process_grant_subscription_type, GrantSubscriptionStates.waiting_for_subscription_type
    )
    dp.message.register(
        process_grant_subscription_confirmation, GrantSubscriptionStates.waiting_for_confirmation
    )

    logger.info("Admin handlers registered")

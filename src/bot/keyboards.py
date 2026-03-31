"""Bot keyboards.

All inline and reply keyboards are centralized here
for easy editing and consistent UI.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

from src.bot.constants import CallbackData


class Keyboards:
    """All bot keyboards."""

    # Main menu keyboard (Reply)
    @staticmethod
    def main_menu() -> ReplyKeyboardMarkup:
        """Main menu reply keyboard."""
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="➕ Пополнить")],
                [KeyboardButton(text="🔗 Рефералы"), KeyboardButton(text="📖 Помощь")],
            ],
            resize_keyboard=True,
        )

    # Deposit method selection
    @staticmethod
    def deposit_methods() -> InlineKeyboardMarkup:
        """Deposit method selection keyboard."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="💳 СБП QR", callback_data=CallbackData.DEPOSIT_SBP),
                    InlineKeyboardButton(text="💳 Карта", callback_data=CallbackData.DEPOSIT_CARD),
                ],
                [InlineKeyboardButton(text="❌ Отмена", callback_data=CallbackData.CANCEL)],
            ]
        )

    # Deposit payment actions
    @staticmethod
    def deposit_payment(payment_url: str, payment_id: int) -> InlineKeyboardMarkup:
        """Keyboard for active payment with payment URL."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=payment_url)],
                [
                    InlineKeyboardButton(
                        text="✅ Проверить статус",
                        callback_data=f"{CallbackData.DEPOSIT_CHECK}:{payment_id}",
                    ),
                    InlineKeyboardButton(text="❌ Отмена", callback_data=CallbackData.CANCEL),
                ],
            ]
        )

    @staticmethod
    def deposit_check_status(payment_id: int) -> InlineKeyboardMarkup:
        """Keyboard to check payment status."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔄 Проверить статус",
                        callback_data=f"{CallbackData.DEPOSIT_CHECK}:{payment_id}",
                    ),
                ],
                [InlineKeyboardButton(text="❌ Закрыть", callback_data=CallbackData.CANCEL)],
            ]
        )

    # Referral keyboard
    @staticmethod
    def referral_menu() -> InlineKeyboardMarkup:
        """Referral menu keyboard."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📋 Статистика", callback_data=CallbackData.REFERRAL_STATS)],
                [InlineKeyboardButton(text="🔗 Получить ссылку", callback_data=CallbackData.REFERRAL_LINK)],
                [InlineKeyboardButton(text="❌ Закрыть", callback_data=CallbackData.CANCEL)],
            ]
        )

    # Cancel keyboard (simple)
    @staticmethod
    def cancel() -> InlineKeyboardMarkup:
        """Simple cancel keyboard."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data=CallbackData.CANCEL)],
            ]
        )

    # Back to menu
    @staticmethod
    def back_to_menu() -> InlineKeyboardMarkup:
        """Back to main menu keyboard."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data=CallbackData.MAIN_MENU)],
            ]
        )

    # Balance actions
    @staticmethod
    def balance_actions() -> InlineKeyboardMarkup:
        """Balance actions keyboard."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="➕ Пополнить", callback_data=CallbackData.DEPOSIT)],
                [InlineKeyboardButton(text="📋 История", callback_data=CallbackData.DEPOSIT_HISTORY)],
            ]
        )

    # Deposit history pagination
    @staticmethod
    def deposit_history_pagination(page: int, total_pages: int) -> InlineKeyboardMarkup:
        """Deposit history pagination keyboard."""
        buttons = []
        if page > 0:
            buttons.append(
                InlineKeyboardButton(text="⬅️", callback_data=f"{CallbackData.DEPOSIT_HISTORY}:{page - 1}")
            )
        if page < total_pages - 1:
            buttons.append(
                InlineKeyboardButton(text="➡️", callback_data=f"{CallbackData.DEPOSIT_HISTORY}:{page + 1}")
            )
        return InlineKeyboardMarkup(
            inline_keyboard=[
                buttons if buttons else [],
                [InlineKeyboardButton(text="❌ Закрыть", callback_data=CallbackData.CANCEL)],
            ]
        )
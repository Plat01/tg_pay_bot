"""Bot keyboards.

All inline and reply keyboards are centralized here
for easy editing and consistent UI.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

from src.bot.constants import CallbackData


class Keyboards:
    """All bot keyboards."""

    # Main menu keyboard (Inline - buttons under message)
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Main menu inline keyboard."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🧪 Тестовая подписка", callback_data=CallbackData.TRIAL_SUBSCRIPTION),
                    InlineKeyboardButton(text="💎 Купить подписку", callback_data=CallbackData.BUY_SUBSCRIPTION),
                ],
                [
                    InlineKeyboardButton(text="💰 Баланс", callback_data=CallbackData.BALANCE),
                    InlineKeyboardButton(text="➕ Пополнить", callback_data=CallbackData.DEPOSIT),
                ],
                [
                    InlineKeyboardButton(text="👥 Пригласить друга", callback_data=CallbackData.REFERRAL),
                    InlineKeyboardButton(text="📖 Помощь", callback_data=CallbackData.HELP),
                ],
            ]
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
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
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
                    InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU),
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
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
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
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
            ]
        )

    # Referral invite keyboard with share button
    @staticmethod
    def referral_invite(referral_link: str) -> InlineKeyboardMarkup:
        """Referral invite keyboard with share button.

        Args:
            referral_link: Full referral link to share.

        Returns:
            InlineKeyboardMarkup with share button.
        """
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📤 Отправить приглашение",
                        switch_inline_query=referral_link,
                    )
                ],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
            ]
        )

    # Cancel keyboard (simple)
    @staticmethod
    def cancel() -> InlineKeyboardMarkup:
        """Simple cancel keyboard."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
            ]
        )

    # Back to menu
    @staticmethod
    def back_to_menu() -> InlineKeyboardMarkup:
        """Back to main menu keyboard."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
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
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
            ]
        )

    # Balance deposit amount selection
    @staticmethod
    def balance_deposit_amounts() -> InlineKeyboardMarkup:
        """Balance deposit amount selection keyboard."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="50 ₽", callback_data=CallbackData.DEPOSIT_AMOUNT_50),
                    InlineKeyboardButton(text="100 ₽", callback_data=CallbackData.DEPOSIT_AMOUNT_100),
                ],
                [
                    InlineKeyboardButton(text="250 ₽", callback_data=CallbackData.DEPOSIT_AMOUNT_250),
                    InlineKeyboardButton(text="500 ₽", callback_data=CallbackData.DEPOSIT_AMOUNT_500),
                ],
                [
                    InlineKeyboardButton(text="1000 ₽", callback_data=CallbackData.DEPOSIT_AMOUNT_1000),
                    InlineKeyboardButton(text="2500 ₽", callback_data=CallbackData.DEPOSIT_AMOUNT_2500),
                ],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
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
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
            ]
        )

    # Trial subscription keyboard
    @staticmethod
    def trial_subscription() -> InlineKeyboardMarkup:
        """Trial subscription keyboard."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Активировать", callback_data=CallbackData.TRIAL_ACTIVATE)],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
            ]
        )

    # Buy subscription tariff selection
    @staticmethod
    def buy_subscription() -> InlineKeyboardMarkup:
        """Buy subscription tariff selection keyboard."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="1 месяц — 299 ₽", callback_data=CallbackData.TARIFF_1_MONTH)],
                [InlineKeyboardButton(text="3 месяца — 799 ₽", callback_data=CallbackData.TARIFF_3_MONTHS)],
                [InlineKeyboardButton(text="12 месяцев — 2499 ₽", callback_data=CallbackData.TARIFF_12_MONTHS)],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
            ]
        )
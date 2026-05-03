"""Bot keyboards.

This module contains all keyboard layouts for the Telegram bot.
"""

import uuid
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot.constants import CallbackData
from src.services.tariff import TariffService
from src.infrastructure.database import async_session_maker
from src.config import settings
from src.infrastructure.payments.schemas import PlategaPaymentMethod


class Keyboards:
    """All bot keyboards."""

    # Main menu keyboard (Inline - buttons under message)
    @staticmethod
    def main_menu(show_trial_button: bool = True) -> InlineKeyboardMarkup:
        """Main menu inline keyboard with optional trial button.

        Args:
            show_trial_button: Whether to show trial subscription button.

        Returns:
            InlineKeyboardMarkup with main menu buttons.
        """
        buttons = [
            [
                InlineKeyboardButton(text="ℹ️ Инфо", callback_data=CallbackData.INFO),
                InlineKeyboardButton(text="💼 Профиль", callback_data=CallbackData.PROFILE),
            ],
            [
                InlineKeyboardButton(text="💳 Оплатить", callback_data=CallbackData.PAY),
                InlineKeyboardButton(text="💰 Баланс", callback_data=CallbackData.BALANCE),
            ],
            [
                InlineKeyboardButton(text="🛠️ Поддержка", callback_data=CallbackData.SUPPORT),
            ],
            [
                InlineKeyboardButton(
                    text="👥 Пригласить друга", callback_data=CallbackData.CONNECT
                ),
            ],
        ]

        if show_trial_button:
            buttons[1].append(
                InlineKeyboardButton(
                    text="🧪 Тестовый период", callback_data=CallbackData.TRIAL_SUBSCRIPTION
                )
            )

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    # Info menu keyboard with legal links
    @staticmethod
    def info_menu() -> InlineKeyboardMarkup:
        """Info menu keyboard with privacy policy and user agreement buttons."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🛡 Политика конф.", url=settings.privacy_policy_link),
                ],
                [
                    InlineKeyboardButton(text="📄 Оферта", url=settings.user_agreement_link),
                ],
                [
                    InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU),
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
                [
                    InlineKeyboardButton(
                        text="📋 Статистика", callback_data=CallbackData.REFERRAL_STATS
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔗 Получить ссылку", callback_data=CallbackData.REFERRAL_LINK
                    )
                ],
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
                [
                    InlineKeyboardButton(text="🛠️ Поддержка", callback_data=CallbackData.SUPPORT),
                    InlineKeyboardButton(
                        text="📋 История", callback_data=CallbackData.DEPOSIT_HISTORY
                    ),
                ],
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
                    InlineKeyboardButton(
                        text="100 ₽", callback_data=CallbackData.DEPOSIT_AMOUNT_100
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="250 ₽", callback_data=CallbackData.DEPOSIT_AMOUNT_250
                    ),
                    InlineKeyboardButton(
                        text="500 ₽", callback_data=CallbackData.DEPOSIT_AMOUNT_500
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="1000 ₽", callback_data=CallbackData.DEPOSIT_AMOUNT_1000
                    ),
                    InlineKeyboardButton(
                        text="2500 ₽", callback_data=CallbackData.DEPOSIT_AMOUNT_2500
                    ),
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
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"{CallbackData.DEPOSIT_HISTORY}:{page - 1}"
                )
            )
        if page < total_pages - 1:
            buttons.append(
                InlineKeyboardButton(
                    text="➡️", callback_data=f"{CallbackData.DEPOSIT_HISTORY}:{page + 1}"
                )
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
        """Trial subscription keyboard with 'Start' button."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Начать", callback_data=CallbackData.TRIAL_ACTIVATE)],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
            ]
        )

    # Buy subscription tariff selection
    @staticmethod
    async def buy_subscription() -> InlineKeyboardMarkup:
        """Buy subscription tariff selection keyboard."""
        async with async_session_maker() as session:
            tariff_service = TariffService(session)
            tariffs = await tariff_service.get_all_tariffs()

        monthly_data = tariffs.get("monthly")
        quarterly_data = tariffs.get("quarterly")
        yearly_data = tariffs.get("yearly")

        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=monthly_data["label"] if monthly_data else "1 месяц — 199 ₽",
                        callback_data=CallbackData.TARIFF_1_MONTH,
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=quarterly_data["label"] if quarterly_data else "3 месяца — 499 ₽",
                        callback_data=CallbackData.TARIFF_3_MONTHS,
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=yearly_data["label"] if yearly_data else "12 месяцев — 1999 ₽",
                        callback_data=CallbackData.TARIFF_12_MONTHS,
                    )
                ],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
            ]
        )

    @staticmethod
    def payment_methods(tariff_type: str) -> InlineKeyboardMarkup:
        """Payment method selection keyboard.

        Args:
            tariff_type: Selected tariff type ('monthly', 'quarterly', 'yearly').

        Returns:
            InlineKeyboardMarkup with payment method buttons.
        """
        buttons = [
            [
                InlineKeyboardButton(
                    text="💰 Баланс",
                    callback_data=f"payment_balance:{tariff_type}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 СБП QR-код",
                    callback_data=f"payment_method:{PlategaPaymentMethod.SBP_QR}:{tariff_type}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Банковская карта РФ",
                    callback_data=f"payment_method:{PlategaPaymentMethod.CARD_ACQUIRING}:{tariff_type}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🌍 Международная карта",
                    callback_data=f"payment_method:{PlategaPaymentMethod.INTERNATIONAL}:{tariff_type}",
                )
            ],
            [
                InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.BUY_SUBSCRIPTION),
            ],
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def error_with_support() -> InlineKeyboardMarkup:
        """Error keyboard with support button.

        Returns:
            InlineKeyboardMarkup with support and back to menu buttons.
        """
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🛠️ Поддержка", callback_data=CallbackData.SUPPORT),
                ],
                [
                    InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU),
                ],
            ]
        )

    @staticmethod
    def error_with_support_link() -> InlineKeyboardMarkup:
        """Error keyboard with direct support link button.

        Returns:
            InlineKeyboardMarkup with support link and back to menu buttons.
        """
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="💬 Написать в поддержку", url=settings.support_link),
                ],
                [
                    InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU),
                ],
            ]
        )

    @staticmethod
    def payment_confirm(
        payment_id: uuid.UUID | str, payment_url: str | None = None
    ) -> InlineKeyboardMarkup:
        """Payment confirmation keyboard with 'I paid' button.

        Args:
            payment_id: Internal payment ID (UUID or string).
            payment_url: Payment URL from provider (optional).

        Returns:
            InlineKeyboardMarkup with payment confirmation buttons.
        """
        buttons = []

        # Add "Go to payment" button if URL exists
        if payment_url:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text="💳 Перейти к оплате",
                        url=payment_url,
                    )
                ]
            )

        # Add "I paid" button
        buttons.append(
            [
                InlineKeyboardButton(
                    text="✅ Я оплатил",
                    callback_data=f"confirm_payment:{payment_id}",
                )
            ]
        )

        # Add cancel button
        buttons.append(
            [
                InlineKeyboardButton(text="◀️ Отмена", callback_data=CallbackData.MAIN_MENU),
            ]
        )

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def balance_insufficient() -> InlineKeyboardMarkup:
        """Balance insufficient keyboard with deposit button."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ Пополнить баланс", callback_data=CallbackData.DEPOSIT
                    )
                ],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.BUY_SUBSCRIPTION)],
            ]
        )

    @staticmethod
    def subscription_links(subscriptions: list) -> InlineKeyboardMarkup:
        """Subscription links keyboard with buttons for each subscription.

        Args:
            subscriptions: List of Subscription objects.

        Returns:
            InlineKeyboardMarkup with buttons for each subscription link.
        """
        buttons = []

        for subscription in subscriptions:
            subscription_type = subscription.subscription_type or "unknown"
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"🔗 {subscription_type}",
                        callback_data=f"{CallbackData.GET_SUBSCRIPTION_LINK}:{subscription.id}",
                    )
                ]
            )

        buttons.append(
            [
                InlineKeyboardButton(
                    text="📖 Инструкция по установке",
                    url="https://telegra.ph/IPhone-04-14-6",
                )
            ]
        )

        buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    @staticmethod
    def subscription_success() -> InlineKeyboardMarkup:
        """Keyboard after successful subscription purchase.

        Returns:
            InlineKeyboardMarkup with instruction and back to menu buttons.
        """
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📖 Инструкция по установке",
                        url="https://telegra.ph/IPhone-04-14-6",
                    )
                ],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=CallbackData.MAIN_MENU)],
            ]
        )

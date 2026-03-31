"""Bot message texts.

All user-facing message texts are centralized here
for easy editing and future localization support.
"""

from src.config import settings


class Texts:
    """All bot message texts."""

    # Start command
    START_WELCOME = (
        "👋 Добро пожаловать!\n\n"
        "Используйте команды для управления балансом:\n"
        "• /balance — проверить баланс\n"
        "• /deposit — пополнить баланс\n"
        "• /referral — реферальная программа"
    )

    START_REFERRAL = (
        "👋 Вы были приглашены пользователем @{referrer_username}!\n\n"
        "Регистрация завершена. Используйте команды для управления балансом."
    )

    # Balance
    BALANCE_INFO = "💰 Ваш баланс: {balance:.2f} ₽"
    BALANCE_ZERO = "💰 Ваш баланс: 0.00 ₽\n\nИспользуйте /deposit для пополнения."

    # Deposit
    DEPOSIT_AMOUNT_PROMPT = "Введите сумму пополнения (минимум {min_amount} ₽):"
    DEPOSIT_METHOD_SELECT = "Выберите способ оплаты:"
    DEPOSIT_CREATING = "⏳ Создаю платеж..."
    DEPOSIT_SUCCESS = (
        "✅ Платёж создан!\n\n"
        "Сумма: {amount:.2f} ₽\n"
        "Способ: {method}\n\n"
        "Нажмите кнопку ниже для оплаты."
    )
    DEPOSIT_PENDING = "⏳ Платёж ожидает оплаты.\n\nСумма: {amount:.2f} ₽"
    DEPOSIT_COMPLETED = "✅ Платёж успешно завершен!\n\nСумма: {amount:.2f} ₽ зачислена на баланс."
    DEPOSIT_FAILED = "❌ Платёж не удался. Попробуйте снова."
    DEPOSIT_CANCELLED = "❌ Платёж отменён."
    DEPOSIT_INVALID_AMOUNT = "❌ Неверная сумма. Введите число от {min_amount} до {max_amount} ₽."
    DEPOSIT_HISTORY_EMPTY = "История платежей пуста."
    DEPOSIT_HISTORY_TITLE = "📋 История платежей:\n\n"

    # Referral
    REFERRAL_INFO = (
        "🔗 Ваша реферальная программа\n\n"
        "Реферальный код: {referral_code}\n"
        "Рефералов: {total_referrals}\n"
        "Заработано: {total_earnings:.2f} ₽\n"
        "Ожидает выплаты: {pending_earnings:.2f} ₽\n\n"
        "Отправьте свой код друзьям и получите {percent}% от их платежей!"
    )
    REFERRAL_LINK = "🔗 Ваша реферальная ссылка:\n\n{link}"
    REFERRAL_STATS_EMPTY = "У вас пока нет рефералов."

    # Errors
    ERROR_GENERIC = "❌ Произошла ошибка. Попробуйте позже."
    ERROR_NOT_REGISTERED = "❌ Вы не зарегистрированы. Используйте /start."
    ERROR_PAYMENT_NOT_FOUND = "❌ Платёж не найден."

    # Cancel
    CANCELLED = "❌ Операция отменена."

    # Help
    HELP_TEXT = (
        "📖 Справка по командам:\n\n"
        "/start — регистрация\n"
        "/balance — баланс\n"
        "/deposit — пополнить баланс\n"
        "/referral — реферальная программа\n"
        "/help — эта справка"
    )


def format_text(template: str, **kwargs) -> str:
    """Format text template with given parameters.

    Args:
        template: Text template from Texts class.
        **kwargs: Parameters to substitute.

    Returns:
        Formatted text string.
    """
    return template.format(**kwargs)
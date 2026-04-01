"""Bot message texts.

All user-facing message texts are centralized here
for easy editing and future localization support.
"""

from src.config import settings


class Texts:
    """All bot message texts."""

    # Start command
    START_WELCOME = (
        "👋 <b>Добро пожаловать!</b>\n\n"
        "Используйте кнопки меню для управления:"
    )

    START_NEW_USER = (
        "👋 <b>Добро пожаловать, {first_name}!</b>\n\n"
        "Вы успешно зарегистрированы.\n\n"
        "Используйте кнопки меню для управления:"
    )

    START_EXISTING_USER = (
        "👋 <b>С возвращением, {first_name}!</b>\n\n"
        "Ваш баланс: {balance} ₽\n\n"
        "Используйте кнопки меню для управления:"
    )

    START_MAIN_MENU = (
        "👋 <b>Главное меню</b>\n\n"
        "Ваш баланс: {balance} ₽\n\n"
        "Используйте кнопки меню для управления:"
    )

    START_REFERRAL = (
        "👋 Вы были приглашены пользователем @{referrer_username}!\n\n"
        "Регистрация завершена. Используйте кнопки меню для управления."
    )

    # Balance
    BALANCE_INFO = (
        "💰 <b>Ваш баланс</b>\n\n"
        "Сумма: {balance} ₽\n"
        "Реферальный код: <code>{referral_code}</code>"
    )
    BALANCE_DEPOSIT_PROMPT = (
        "💳 <b>Пополнение баланса</b>\n\n"
        "Выберите сумму или используйте команду <code>/deposit &lt;rub&gt;</code>"
    )
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
        "👥 <b>Реферальная программа</b>\n\n"
        "• Новый пользователь получает: <b>5 ₽</b> при первом пополнении от 120 ₽\n"
        "• Вы получаете при первом пополнении реферала: <b>10 ₽</b>\n"
        "• Комиссия с каждого пополнения реферала: <b>20%</b>\n\n"
        "🤖 <b>Ссылка на бота:</b>\n"
        "{bot_link}?start={referral_code}\n\n"
        "🆔 <b>Ваш код:</b> <code>{referral_code}</code>\n\n"
        "📢 Приглашайте друзей и зарабатывайте!"
    )
    # Text for sharing referral link (sent when user clicks "Отправить приглашение")
    REFERRAL_SHARE = (
        "🎉 <b>Присоединяйся к VPN сервису!</b>\n\n"
        "💎 При первом пополнении от 120 ₽ ты получишь <b>5 ₽</b> бонусом на баланс!\n\n"
        "🚀 Быстрое подключение\n"
        "🌍 Серверы по всему миру\n"
        "🔒 Надежная защита\n\n"
        "👇 Переходи по ссылке:\n"
        "{referral_link}"
    )
    REFERRAL_LINK = "🔗 Ваша реферальная ссылка:\n\n{link}"
    REFERRAL_STATS_EMPTY = "У вас пока нет рефералов."

    # Errors
    ERROR_GENERIC = "❌ Произошла ошибка. Попробуйте позже."
    ERROR_NOT_REGISTERED = "❌ Вы не зарегистрированы.\nИспользуйте /start для регистрации."
    ERROR_PAYMENT_NOT_FOUND = "❌ Платёж не найден."
    ERROR_BALANCE = "❌ Ошибка получения баланса"

    # Deposit messages
    DEPOSIT_PROMPT = "💳 <b>Пополнение баланса</b>\n\nДля пополнения используйте команду /deposit"

    # Subscription messages
    TRIAL_SUBSCRIPTION = (
        "🧪 <b>Тестовая подписка</b>\n\n"
        "Вы можете активировать тестовую подписку на 3 дня.\n\n"
        "Для активации нажмите кнопку ниже."
    )
    BUY_SUBSCRIPTION = (
        "💎 <b>Купить подписку</b>\n\n"
        "Выберите тарифный план:\n\n"
        "• 1 месяц — 299 ₽\n"
        "• 3 месяца — 799 ₽\n"
        "• 12 месяцев — 2499 ₽\n\n"
        "Для покупки выберите тариф."
    )

    # Cancel
    CANCELLED = "❌ Операция отменена."

    # Help
    HELP_TEXT = (
        "📖 <b>Справка по командам:</b>\n\n"
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
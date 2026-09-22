"""Bot constants.

All callback data strings, command names, and other constants
are centralized here to avoid typos and ensure consistency.
"""

from src.config import settings
from src.infrastructure.payments import PaymentMethodKind
from src.services.tariff import get_tariff_names


class CallbackData:
    """Callback data constants for inline keyboards."""

    # Navigation
    CANCEL = "cancel"
    MAIN_MENU = "main_menu"

    # Main menu buttons
    INFO = "info"
    PROFILE = "profile"
    PAY = "pay"
    SUPPORT = "support"
    BONUSES = "bonuses"
    CONNECT = "connect"

    # Deposit
    DEPOSIT = "deposit"
    DEPOSIT_SBP = "deposit_sbp"
    DEPOSIT_CARD = "deposit_card"
    DEPOSIT_CHECK = "deposit_check"  # Format: deposit_check:{payment_id}
    DEPOSIT_HISTORY = "deposit_history"  # Format: deposit_history:{page}

    # Referral
    REFERRAL = "referral"
    REFERRAL_STATS = "referral_stats"
    REFERRAL_LINK = "referral_link"

    # Balance
    BALANCE = "balance"

    # Help
    HELP = "help"

    # Subscription
    TRIAL_SUBSCRIPTION = "trial_subscription"
    TRIAL_ACTIVATE = "trial_activate"
    BUY_SUBSCRIPTION = "buy_subscription"
    GET_SUBSCRIPTION_LINK = "get_sub_link"  # Format: get_sub_link:{subscription_id}

    # Tariffs
    TARIFF_SELECT = "tariff_select"  # Format: tariff_select:{tariff_type}

    # Legacy tariff callbacks (kept for buttons in old, already sent messages)
    TARIFF_1_MONTH = "tariff_1_month"
    TARIFF_3_MONTHS = "tariff_3_months"
    TARIFF_12_MONTHS = "tariff_12_months"

    # Payment confirmation
    CONFIRM_PAYMENT = "confirm_payment"  # Format: confirm_payment:{payment_id}
    # Format: payment_method:{provider}:{code}:{tariff_type}
    PAYMENT_METHOD_SELECT = "payment_method"
    DEPOSIT_METHOD = "method"  # Format: method:{provider}:{code}
    PAYMENT_BALANCE = "payment_balance"  # Format: payment_balance:{tariff_type}

    # Admin
    SEND_SUBSCRIPTION_LINKS = "send_subscription_links"

    # Deposit amounts
    DEPOSIT_AMOUNT_50 = "deposit_50"
    DEPOSIT_AMOUNT_100 = "deposit_100"
    DEPOSIT_AMOUNT_250 = "deposit_250"
    DEPOSIT_AMOUNT_500 = "deposit_500"
    DEPOSIT_AMOUNT_1000 = "deposit_1000"
    DEPOSIT_AMOUNT_2500 = "deposit_2500"


class Commands:
    """Bot command constants."""

    START = "start"
    HELP = "help"
    BALANCE = "balance"
    DEPOSIT = "deposit"
    REFERRAL = "referral"
    ALL_MESSAGE = "all_message"
    PAID_MESSAGE = "pay_message"
    SUBSCRIPTIONS = "subscriptions"
    USER_PAYMENTS = "payments"
    PAYMENT_BY_EXTERNAL_ID = "payment_by_ext"
    ADD_BALANCE = "add_balance"
    GRANT_SUBSCRIPTION = "grant_subscription"
    TARIFFS = "tariffs"
    ADD_TARIFF = "add_tariff"
    PAYMENT_METHODS = "payment_methods"


class Limits:
    """Limits and constraints for bot operations."""

    MIN_DEPOSIT_AMOUNT = 100  # Minimum deposit in RUB
    MAX_DEPOSIT_AMOUNT = 100000  # Maximum deposit in RUB
    MAX_HISTORY_PAGE_SIZE = 10  # Maximum payments per history page


class Emoji:
    """Emoji constants for messages."""

    MONEY = "💰"
    PLUS = "➕"
    LINK = "🔗"
    CARD = "💳"
    CHECK = "✅"
    CROSS = "❌"
    CLOCK = "⏳"
    BOOK = "📖"
    HOME = "🏠"
    LIST = "📋"
    ARROW_LEFT = "⬅️"
    ARROW_RIGHT = "➡️"
    REFRESH = "🔄"
    WAVE = "👋"

    # New emoji for main menu
    INFO = "ℹ️"
    PROFILE = "💼"
    PAY = "💳"
    SUPPORT = "🛠️"
    BONUSES = "🎁"
    CONNECT = "🔗"
    USER = "👤"
    CALENDAR = "📅"
    DEVICES = "📱"


# Legacy callback data -> tariff type (buttons from messages sent before
# tariffs became dynamic).
LEGACY_CALLBACK_TARIFFS = {
    CallbackData.TARIFF_1_MONTH: "monthly",
    CallbackData.TARIFF_3_MONTHS: "quarterly",
    CallbackData.TARIFF_12_MONTHS: "yearly",
}


def build_tariff_callback(tariff_type: str) -> str:
    """Build callback data for a tariff button."""
    return f"{CallbackData.TARIFF_SELECT}:{tariff_type}"


def parse_tariff_callback(callback_data: str | None) -> str | None:
    """Get tariff type from callback data (dynamic or legacy)."""
    if not callback_data:
        return None

    if callback_data.startswith(f"{CallbackData.TARIFF_SELECT}:"):
        return callback_data.split(":", 1)[1] or None

    return LEGACY_CALLBACK_TARIFFS.get(callback_data)


# --- Способы оплаты -------------------------------------------------------
#
# Кнопка соответствует типу способа оплаты (СБП, карта, крипта), а не
# конкретному провайдеру: провайдер выбирается по приоритету в момент
# нажатия. Актуальный формат callback data:
#   payment_method:{kind}:{tariff_type}  — оплата подписки
#   method:{kind}                        — пополнение баланса
#
# В уже отправленных сообщениях остаются кнопки старых форматов
# (payment_method:{provider}:{code}:{tariff_type} и payment_method:{code}:{tariff_type}),
# они разбираются в селектор вида "provider:code".


def build_payment_method_callback(kind: PaymentMethodKind, tariff_type: str) -> str:
    """Build callback data for a subscription payment method button."""
    return f"{CallbackData.PAYMENT_METHOD_SELECT}:{kind.value}:{tariff_type}"


def build_deposit_method_callback(kind: PaymentMethodKind) -> str:
    """Build callback data for a deposit payment method button."""
    return f"{CallbackData.DEPOSIT_METHOD}:{kind.value}"


def _build_selector(parts: list[str]) -> str | None:
    """Build a payment method selector from the middle part of callback data.

    A selector is either a method kind ("sbp") or a "provider:code" pair
    ("platega:2") coming from a button of an older format.

    Args:
        parts: Callback data parts between the prefix and the tariff type.

    Returns:
        Selector string or None if the parts make no sense.
    """
    # Новый формат: тип способа оплаты
    if len(parts) == 1:
        if parts[0] in {kind.value for kind in PaymentMethodKind}:
            return parts[0]

        # Старый формат: только код способа у провайдера по умолчанию
        if parts[0].isdigit():
            return f"{settings.default_payment_provider}:{parts[0]}"

        return None

    # Старый формат: провайдер и его код
    if len(parts) == 2 and parts[0] and parts[1]:
        return f"{parts[0]}:{parts[1]}"

    return None


def parse_payment_method_callback(callback_data: str | None) -> tuple[str, str] | None:
    """Parse subscription payment method callback data.

    Args:
        callback_data: Raw callback data from the button.

    Returns:
        Tuple of (payment method selector, tariff type) or None if the data
        has an unexpected format.
    """
    if not callback_data:
        return None

    parts = callback_data.split(":")
    if parts[0] != CallbackData.PAYMENT_METHOD_SELECT or len(parts) < 3:
        return None

    selector = _build_selector(parts[1:-1])
    tariff_type = parts[-1]

    if not selector or not tariff_type:
        return None

    return selector, tariff_type


def parse_deposit_method_callback(callback_data: str | None) -> str | None:
    """Parse deposit payment method callback data.

    Args:
        callback_data: Raw callback data from the button.

    Returns:
        Payment method selector or None if the data has an unexpected format
        (including the "method:cancel" button).
    """
    if not callback_data:
        return None

    parts = callback_data.split(":")
    if parts[0] != CallbackData.DEPOSIT_METHOD or len(parts) < 2:
        return None

    if parts[1] == "cancel":
        return None

    return _build_selector(parts[1:])


UNKNOWN_SUBSCRIPTION_LABEL = "Неизвестно"


def get_subscription_type_label(subscription_type: str | None) -> str:
    """Get Russian label for subscription type.

    Args:
        subscription_type: Subscription type in English (trial, monthly, etc.)

    Returns:
        Russian label for subscription type.
    """
    if not subscription_type:
        return UNKNOWN_SUBSCRIPTION_LABEL
    return get_tariff_names().get(subscription_type, subscription_type)

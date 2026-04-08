"""Bot constants.

All callback data strings, command names, and other constants
are centralized here to avoid typos and ensure consistency.
"""


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

    # Tariffs
    TARIFF_1_MONTH = "tariff_1_month"
    TARIFF_3_MONTHS = "tariff_3_months"
    TARIFF_12_MONTHS = "tariff_12_months"

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
    SEND_SUBSCRIPTION_LINKS = "send_sub_links"


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

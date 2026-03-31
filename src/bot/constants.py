"""Bot constants.

All callback data strings, command names, and other constants
are centralized here to avoid typos and ensure consistency.
"""


class CallbackData:
    """Callback data constants for inline keyboards."""

    # Navigation
    CANCEL = "cancel"
    MAIN_MENU = "main_menu"

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


class Commands:
    """Bot command constants."""

    START = "start"
    HELP = "help"
    BALANCE = "balance"
    DEPOSIT = "deposit"
    REFERRAL = "referral"


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
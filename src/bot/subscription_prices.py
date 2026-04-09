"""Subscription prices and Duration Configuration.

This module contains all subscription tariff information:
prices, duration, and display labels.

Note: Monthly price is set to 50 ₽ for testing purposes.
It should be changed to 299 ₽ after testing.
"""

from typing import Dict, Any


SUBSCRIPTION_PRICES: Dict[str, Dict[str, Any]] = {
    "monthly": {
        "price": 50,  # TODO: Test price - change to 299 after testing
        "days": 30,
        "label": "1 месяц — 50 ₽",
        "tariff_type": "monthly",
    },
    "quarterly": {
        "price": 799,
        "days": 90,
        "label": "3 месяца — 799 ₽",
        "tariff_type": "quarterly",
    },
    "yearly": {
        "price": 2499,
        "days": 365,
        "label": "12 месяцев — 2499 ₽",
        "tariff_type": "yearly",
    },
}


def get_tariff_by_price(price: int) -> str | None:
    """Get tariff type by price amount.

    Args:
        price: Payment amount in rubles.

    Returns:
        Tariff type string ('monthly', 'quarterly', 'yearly') or None if not found.
    """
    for tariff_type, data in SUBSCRIPTION_PRICES.items():
        if data["price"] == price:
            return tariff_type
    return None


def get_tariff_data(tariff_type: str) -> Dict[str, Any] | None:
    """Get tariff data by tariff type.

    Args:
        tariff_type: Tariff type string ('monthly', 'quarterly', 'yearly').

    Returns:
        Dictionary with price, days, label or None if not found.
    """
    return SUBSCRIPTION_PRICES.get(tariff_type)


def get_all_tariffs() -> Dict[str, Dict[str, Any]]:
    """Get all available tariffs.

    Returns:
        Dictionary with all tariff types and their data.
    """
    return SUBSCRIPTION_PRICES

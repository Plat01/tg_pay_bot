"""Tariff service with caching.

Prices are stored in DEFAULT_PRICES and can be overridden via database
(if tariff_settings table exists in future).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PRICES = {
    "trial": {"price": 0.0, "days": 3},
    "monthly": {"price": 199.0, "days": 30},
    "quarterly": {"price": 499.0, "days": 90},
    "yearly": {"price": 1999.0, "days": 365},
}

TARIFF_DURATION_DAYS = {
    tariff_type: data["days"] for tariff_type, data in DEFAULT_PRICES.items()
}


def get_tariff_type_by_days(days: int) -> str:
    """Determine subscription type based on duration days.

    Rules:
    - days < 4: trial
    - 4 <= days < 30: monthly
    - 30 <= days < 90: quarterly
    - 90+ days: yearly

    Args:
        days: Number of subscription days.

    Returns:
        Subscription type string.
    """
    if days < 4:
        return "trial"
    elif days < 30:
        return "monthly"
    elif days < 90:
        return "quarterly"
    else:
        return "yearly"


class TariffService:
    """Service for managing subscription tariffs.

    Prices are from DEFAULT_PRICES constants.
    In future can be extended to load from database (tariff_settings table).
    """

    _cache: dict[str, dict[str, Any]] = {}

    def __init__(self, session: Any = None) -> None:
        """Initialize service.

        Args:
            session: Database session (optional, for future DB-backed settings).
        """
        self.session = session

    @classmethod
    async def initialize_cache(cls) -> None:
        """Initialize cache at bot startup.

        Currently just loads DEFAULT_PRICES into cache.
        In future can load from database.
        """
        cls._cache = {}
        for tariff_type, data in DEFAULT_PRICES.items():
            cls._cache[tariff_type] = {
                "price": data["price"],
                "days": data["days"],
                "label": cls._build_label(tariff_type, data["price"]),
                "tariff_type": tariff_type,
            }

        logger.info(f"Tariff cache initialized: {len(cls._cache)} tariffs loaded")

    async def refresh_cache(self) -> None:
        """Refresh cache from database (instance method).

        Currently just reloads DEFAULT_PRICES.
        """
        TariffService._cache = {}
        for tariff_type, data in DEFAULT_PRICES.items():
            TariffService._cache[tariff_type] = {
                "price": data["price"],
                "days": data["days"],
                "label": self._build_label(tariff_type, data["price"]),
                "tariff_type": tariff_type,
            }

        logger.info(f"Tariff cache refreshed: {len(TariffService._cache)} tariffs loaded")

    @staticmethod
    def _build_label(tariff_type: str, price: float) -> str:
        """Build display label for tariff."""
        duration_text = {
            "trial": "3 дня (тест)",
            "monthly": "1 месяц",
            "quarterly": "3 месяца",
            "yearly": "1 год",
        }
        devices_text = {
            "trial": "1 устройство",
            "monthly": "1 устройство",
            "quarterly": "1 устройство",
            "yearly": "1 устройство",
        }
        duration = duration_text.get(tariff_type, f"{DEFAULT_PRICES.get(tariff_type, {}).get('days', 0)} дней")
        devices = devices_text.get(tariff_type, "1 устройство")
        if price == 0:
            return f"{duration} | {devices} • Бесплатно"
        return f"{duration} | {devices} • {int(price)} RUB"

    async def get_tariff_data(self, tariff_type: str) -> dict[str, Any] | None:
        """Get tariff data by type.

        Returns cached data or default values if not found.
        """
        if tariff_type in TariffService._cache:
            return TariffService._cache[tariff_type]

        if tariff_type in DEFAULT_PRICES:
            default = DEFAULT_PRICES[tariff_type]
            return {
                "price": default["price"],
                "days": default["days"],
                "label": self._build_label(tariff_type, default["price"]),
                "tariff_type": tariff_type,
            }

        return None

    async def get_all_tariffs(self) -> dict[str, dict[str, Any]]:
        """Get all tariffs (from cache + defaults)."""
        result = {}

        for tariff_type, data in DEFAULT_PRICES.items():
            if tariff_type != "trial":
                result[tariff_type] = {
                    "price": data["price"],
                    "days": data["days"],
                    "label": self._build_label(tariff_type, data["price"]),
                    "tariff_type": tariff_type,
                }

        for tariff_type, data in TariffService._cache.items():
            if tariff_type != "trial":
                result[tariff_type] = data

        return result

    async def get_tariff_by_price(self, price: int) -> str | None:
        """Get tariff type by price amount."""
        for tariff_type, data in TariffService._cache.items():
            if int(data["price"]) == price:
                return tariff_type

        for tariff_type, default in DEFAULT_PRICES.items():
            if int(default["price"]) == price:
                return tariff_type

        return None

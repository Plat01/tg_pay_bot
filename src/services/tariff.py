"""Tariff service with caching.

Single source of truth for tariffs is the TARIFFS table below: price,
duration, display texts and device limits. To change prices or durations,
edit TARIFFS only — everything else (keyboards, texts, VPN key TTL,
subscription labels) is derived from it.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

TRIAL_TARIFF = "trial"

# Single source of truth for all tariffs.
#
# price       — price in RUB (must be unique: incoming payments are matched by amount)
# days        — subscription duration in days
# max_grant_days — inclusive upper bound of manual day grants mapped to this tariff
#                  (None for the last tariff, which catches everything above)
# duration_text / devices — used to build button labels
# label       — Russian name of the subscription type
TARIFFS: dict[str, dict[str, Any]] = {
    "trial": {
        "price": 0.0,
        "days": 3,
        "max_grant_days": 3,
        "duration_text": "3 дня (тест)",
        "devices": 1,
        "label": "Триал",
    },
    "monthly": {
        "price": 199.0,
        "days": 30,
        "max_grant_days": 29,
        "duration_text": "1 месяц",
        "devices": 2,
        "label": "Месячная",
    },
    "quarterly": {
        "price": 499.0,
        "days": 90,
        "max_grant_days": 89,
        "duration_text": "3 месяца",
        "devices": 2,
        "label": "Квартальная",
    },
    "yearly": {
        "price": 1999.0,
        "days": 365,
        "max_grant_days": None,
        "duration_text": "1 год",
        "devices": 2,
        "label": "Годовая",
    },
}

# Paid tariffs in display order (everything except trial).
PAID_TARIFF_TYPES = [tariff_type for tariff_type in TARIFFS if tariff_type != TRIAL_TARIFF]

TARIFF_DURATION_DAYS = {tariff_type: data["days"] for tariff_type, data in TARIFFS.items()}

# Duration in days and hours (hours are used as VPN key TTL).
TARIFF_DURATION = {
    tariff_type: {"days": data["days"], "hours": data["days"] * 24}
    for tariff_type, data in TARIFFS.items()
}

TARIFF_LABELS = {tariff_type: data["label"] for tariff_type, data in TARIFFS.items()}


def build_tariff_label(tariff_type: str) -> str:
    """Build display label for a tariff button."""
    data = TARIFFS.get(tariff_type)
    if not data:
        return tariff_type

    devices_count = data["devices"]
    devices = f"{devices_count} устройство" if devices_count == 1 else f"{devices_count} устройства"
    price = data["price"]
    if price == 0:
        return f"{data['duration_text']} | {devices} • Бесплатно"
    return f"{data['duration_text']} | {devices} • {int(price)} RUB"


def _tariff_entry(tariff_type: str) -> dict[str, Any]:
    """Build cache/response entry for a tariff."""
    data = TARIFFS[tariff_type]
    return {
        "price": data["price"],
        "days": data["days"],
        "label": build_tariff_label(tariff_type),
        "tariff_type": tariff_type,
    }


def get_tariff_type_by_days(days: int) -> str:
    """Determine subscription type based on duration days.

    Each tariff covers days up to its ``max_grant_days`` (inclusive); the last
    tariff catches everything above. With the default table that means:
    <= 3 → trial, <= 29 → monthly, <= 89 → quarterly, otherwise yearly.

    Args:
        days: Number of subscription days.

    Returns:
        Subscription type string.
    """
    last_tariff_type = tariff_type = next(iter(TARIFFS))
    for tariff_type, data in TARIFFS.items():
        max_grant_days = data["max_grant_days"]
        if max_grant_days is not None and days <= max_grant_days:
            return tariff_type
        last_tariff_type = tariff_type

    return last_tariff_type


class TariffService:
    """Service for managing subscription tariffs.

    Tariffs are read from the TARIFFS table.
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
    def _load_cache(cls) -> None:
        """Fill cache from the TARIFFS table."""
        cls._cache = {tariff_type: _tariff_entry(tariff_type) for tariff_type in TARIFFS}

    @classmethod
    async def initialize_cache(cls) -> None:
        """Initialize cache at bot startup.

        In future can load from database.
        """
        cls._load_cache()
        logger.info(f"Tariff cache initialized: {len(cls._cache)} tariffs loaded")

    async def refresh_cache(self) -> None:
        """Refresh cache (instance method)."""
        TariffService._load_cache()
        logger.info(f"Tariff cache refreshed: {len(TariffService._cache)} tariffs loaded")

    async def get_tariff_data(self, tariff_type: str) -> dict[str, Any] | None:
        """Get tariff data by type.

        Returns cached data or values from the TARIFFS table if cache is empty.
        """
        if tariff_type in TariffService._cache:
            return TariffService._cache[tariff_type]

        if tariff_type in TARIFFS:
            return _tariff_entry(tariff_type)

        return None

    async def get_all_tariffs(self) -> dict[str, dict[str, Any]]:
        """Get all paid tariffs (trial excluded)."""
        return {
            tariff_type: TariffService._cache.get(tariff_type) or _tariff_entry(tariff_type)
            for tariff_type in PAID_TARIFF_TYPES
        }

    async def get_tariff_by_price(self, price: int) -> str | None:
        """Get tariff type by price amount."""
        for tariff_type, data in TARIFFS.items():
            if int(data["price"]) == price:
                return tariff_type

        return None

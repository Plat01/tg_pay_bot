"""Tariff service backed by the database with an in-memory cache.

Tariffs live in the ``tariff_settings`` table and are edited by admins via the
/tariffs and /add_tariff commands. The TARIFFS dict below holds the defaults:
they are seeded into an empty table on the first bot start and are also used as
a fallback when the cache has not been initialized yet.

Everything else (keyboards, texts, VPN key TTL, subscription labels) reads the
cache through the helpers in this module, so a tariff change takes effect right
after TariffService.refresh_cache().
"""

import logging
import re
from typing import Any

from src.infrastructure.database import async_session_maker
from src.infrastructure.database.repositories import TariffRepository

logger = logging.getLogger(__name__)

TRIAL_TARIFF = "trial"

TARIFF_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,29}$")

MAX_TEXT_LENGTH = 64
MAX_DAYS = 3650
MAX_DEVICES = 50
MAX_PRICE = 1_000_000

# Default tariffs. Seeded into the tariff_settings table when it is empty.
#
# price          — price in RUB (must be unique: payments without stored tariff
#                  metadata are matched by amount)
# days           — subscription duration in days
# max_grant_days — inclusive upper bound of manual day grants mapped to this
#                  tariff (None for the catch-all tariff with the longest term)
# duration_text / devices — used to build button labels
# label          — Russian name of the subscription type
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

EDITABLE_FIELDS = ("price", "days", "devices", "duration_text", "label", "max_grant_days")

FIELD_TITLES = {
    "price": "Цена",
    "days": "Длительность (дней)",
    "devices": "Устройств",
    "duration_text": "Текст длительности",
    "label": "Название типа",
    "max_grant_days": "Макс. дней ручной выдачи",
    "is_active": "Активен",
    "sort_order": "Порядок",
}


class TariffValidationError(ValueError):
    """Raised when admin input for a tariff is invalid."""


def _devices_text(devices: int) -> str:
    """Build 'N устройство/устройства/устройств' text."""
    tens = devices % 100
    ones = devices % 10

    if 11 <= tens <= 14:
        word = "устройств"
    elif ones == 1:
        word = "устройство"
    elif 2 <= ones <= 4:
        word = "устройства"
    else:
        word = "устройств"

    return f"{devices} {word}"


def build_button_label(duration_text: str, devices: int, price: float) -> str:
    """Build display label for a tariff button."""
    devices_part = _devices_text(devices)
    if price == 0:
        return f"{duration_text} | {devices_part} • Бесплатно"
    return f"{duration_text} | {devices_part} • {int(price)} RUB"


def _make_entry(tariff_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Build a cache entry from raw tariff fields."""
    return {
        "tariff_type": tariff_type,
        "price": float(data["price"]),
        "days": int(data["days"]),
        "max_grant_days": data.get("max_grant_days"),
        "duration_text": data["duration_text"],
        "devices": int(data["devices"]),
        "name": data["label"],
        "label": build_button_label(data["duration_text"], int(data["devices"]), data["price"]),
        "sort_order": int(data.get("sort_order", 0)),
        "is_active": bool(data.get("is_active", True)),
    }


def _default_entries() -> dict[str, dict[str, Any]]:
    """Build entries from the TARIFFS defaults."""
    return {
        tariff_type: _make_entry(tariff_type, {**data, "sort_order": index})
        for index, (tariff_type, data) in enumerate(TARIFFS.items())
    }


def get_tariffs() -> dict[str, dict[str, Any]]:
    """Get all tariffs (cache, or defaults when cache is not initialized)."""
    return TariffService._cache or _default_entries()


def get_tariff(tariff_type: str) -> dict[str, Any] | None:
    """Get one tariff entry by type."""
    return get_tariffs().get(tariff_type)


def get_active_tariffs() -> dict[str, dict[str, Any]]:
    """Get active tariffs, trial included."""
    return {
        tariff_type: entry for tariff_type, entry in get_tariffs().items() if entry["is_active"]
    }


def get_paid_tariffs() -> dict[str, dict[str, Any]]:
    """Get active paid tariffs (trial excluded), in display order."""
    return {
        tariff_type: entry
        for tariff_type, entry in get_active_tariffs().items()
        if tariff_type != TRIAL_TARIFF
    }


def get_tariff_days(tariff_type: str) -> int | None:
    """Get subscription duration in days for a tariff."""
    entry = get_tariff(tariff_type)
    return entry["days"] if entry else None


def get_tariff_duration(tariff_type: str) -> dict[str, int] | None:
    """Get duration in days and hours (hours are used as VPN key TTL)."""
    entry = get_tariff(tariff_type)
    if not entry:
        return None
    return {"days": entry["days"], "hours": entry["days"] * 24}


def get_tariff_devices(tariff_type: str) -> int | None:
    """Get device limit for a tariff."""
    entry = get_tariff(tariff_type)
    return entry["devices"] if entry else None


def get_tariff_names() -> dict[str, str]:
    """Get Russian names of subscription types by tariff code."""
    return {tariff_type: entry["name"] for tariff_type, entry in get_tariffs().items()}


def get_tariff_type_by_days(days: int) -> str:
    """Determine subscription type based on duration days.

    Tariffs are checked from the shortest to the longest: the first one whose
    ``max_grant_days`` covers the requested days wins, and the longest tariff
    catches everything above. With the default table that means:
    <= 3 → trial, <= 29 → monthly, <= 89 → quarterly, otherwise yearly.

    Args:
        days: Number of subscription days.

    Returns:
        Subscription type string.
    """
    tariffs = get_tariffs()
    ordered = sorted(tariffs.items(), key=lambda item: item[1]["days"])

    for tariff_type, entry in ordered:
        max_grant_days = entry["max_grant_days"]
        if max_grant_days is not None and days <= max_grant_days:
            return tariff_type

    return ordered[-1][0]


def validate_tariff_field(field: str, raw_value: str) -> Any:
    """Validate and convert one admin-entered tariff field.

    Args:
        field: Field name from EDITABLE_FIELDS (or tariff_type).
        raw_value: Raw text entered by admin.

    Returns:
        Converted value ready to be stored.

    Raises:
        TariffValidationError: If the value is not acceptable.
    """
    value = raw_value.strip()

    if field == "tariff_type":
        value = value.lower()
        if not TARIFF_TYPE_PATTERN.match(value):
            raise TariffValidationError(
                "Код тарифа: 2-30 символов, латиница в нижнем регистре, цифры и _, "
                "начинается с буквы (например, half_year)."
            )
        return value

    if field == "price":
        try:
            price = float(value.replace(",", "."))
        except ValueError as e:
            raise TariffValidationError("Цена должна быть числом, например 299 или 299.50") from e
        if price < 0 or price > MAX_PRICE:
            raise TariffValidationError(f"Цена должна быть от 0 до {MAX_PRICE}.")
        return round(price, 2)

    if field == "days":
        try:
            days = int(value)
        except ValueError as e:
            raise TariffValidationError("Количество дней должно быть целым числом.") from e
        if days < 1 or days > MAX_DAYS:
            raise TariffValidationError(f"Количество дней должно быть от 1 до {MAX_DAYS}.")
        return days

    if field == "devices":
        try:
            devices = int(value)
        except ValueError as e:
            raise TariffValidationError("Количество устройств должно быть целым числом.") from e
        if devices < 1 or devices > MAX_DEVICES:
            raise TariffValidationError(f"Количество устройств должно быть от 1 до {MAX_DEVICES}.")
        return devices

    if field == "max_grant_days":
        if value.lower() in ("-", "нет", "none", "0"):
            return None
        try:
            max_grant_days = int(value)
        except ValueError as e:
            raise TariffValidationError(
                "Введите целое число дней или '-' чтобы тариф покрывал всё сверху."
            ) from e
        if max_grant_days < 1 or max_grant_days > MAX_DAYS:
            raise TariffValidationError(f"Значение должно быть от 1 до {MAX_DAYS} или '-'.")
        return max_grant_days

    if field in ("duration_text", "label"):
        if not value:
            raise TariffValidationError("Текст не может быть пустым.")
        if len(value) > MAX_TEXT_LENGTH:
            raise TariffValidationError(f"Не длиннее {MAX_TEXT_LENGTH} символов.")
        if any(char in value for char in "<>&"):
            raise TariffValidationError("Символы < > & запрещены — они ломают разметку сообщений.")
        return value

    raise TariffValidationError(f"Неизвестное поле: {field}")


class TariffService:
    """Service for managing subscription tariffs stored in the database."""

    _cache: dict[str, dict[str, Any]] = {}

    def __init__(self, session: Any = None) -> None:
        """Initialize service.

        Args:
            session: Database session (optional; own session is opened if absent).
        """
        self.session = session

    @classmethod
    async def initialize_cache(cls) -> None:
        """Seed defaults if needed and load tariffs into the cache at startup.

        If the database is unreachable the bot still starts: helpers fall back
        to the TARIFFS defaults until the cache is loaded.
        """
        try:
            async with async_session_maker() as session:
                repository = TariffRepository(session)

                if await repository.count() == 0:
                    await repository.create_many(
                        [
                            {
                                "tariff_type": tariff_type,
                                "price": float(data["price"]),
                                "days": int(data["days"]),
                                "max_grant_days": data["max_grant_days"],
                                "duration_text": data["duration_text"],
                                "devices": int(data["devices"]),
                                "label": data["label"],
                                "sort_order": index,
                                "is_active": True,
                            }
                            for index, (tariff_type, data) in enumerate(TARIFFS.items())
                        ]
                    )
                    logger.info(f"Tariff table seeded with {len(TARIFFS)} default tariffs")

                await cls._load_cache(session)
        except Exception as e:
            logger.error(f"Failed to load tariffs from database, using defaults: {e}")
            return

        logger.info(f"Tariff cache initialized: {len(cls._cache)} tariffs loaded")

    @classmethod
    async def _load_cache(cls, session: Any) -> None:
        """Load tariffs from the database into the cache."""
        repository = TariffRepository(session)
        rows = await repository.get_all()

        cls._cache = {
            row.tariff_type: _make_entry(
                row.tariff_type,
                {
                    "price": row.price,
                    "days": row.days,
                    "max_grant_days": row.max_grant_days,
                    "duration_text": row.duration_text,
                    "devices": row.devices,
                    "label": row.label,
                    "sort_order": row.sort_order,
                    "is_active": row.is_active,
                },
            )
            for row in rows
        }

    async def refresh_cache(self) -> None:
        """Reload tariffs from the database."""
        if self.session is not None:
            await TariffService._load_cache(self.session)
        else:
            async with async_session_maker() as session:
                await TariffService._load_cache(session)

        logger.info(f"Tariff cache refreshed: {len(TariffService._cache)} tariffs loaded")

    async def _repository(self, session: Any) -> TariffRepository:
        """Build repository for a session."""
        return TariffRepository(session)

    async def get_tariff_data(self, tariff_type: str) -> dict[str, Any] | None:
        """Get tariff data by type (cache, or defaults when cache is empty)."""
        return get_tariff(tariff_type)

    async def get_all_tariffs(self) -> dict[str, dict[str, Any]]:
        """Get all active paid tariffs (trial excluded)."""
        return get_paid_tariffs()

    async def get_tariff_by_price(self, price: int) -> str | None:
        """Get tariff type by price amount.

        Used as a fallback for payments created before tariff metadata was stored.
        """
        for tariff_type, entry in get_tariffs().items():
            if int(entry["price"]) == price:
                return tariff_type

        return None

    async def list_tariffs(self) -> list[dict[str, Any]]:
        """Get all tariffs (including inactive) in display order."""
        return sorted(
            get_tariffs().values(), key=lambda entry: (entry["days"], entry["sort_order"])
        )

    async def create_tariff(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Create a new tariff and refresh the cache.

        Args:
            fields: tariff_type, price, days, devices, duration_text, label
                and optionally max_grant_days.

        Returns:
            Created tariff entry.

        Raises:
            TariffValidationError: If the tariff conflicts with an existing one.
        """
        tariff_type = fields["tariff_type"]

        async with async_session_maker() as session:
            repository = TariffRepository(session)

            if await repository.get_by_type(tariff_type):
                raise TariffValidationError(f"Тариф с кодом {tariff_type} уже существует.")

            await self._ensure_price_is_free(repository, float(fields["price"]), tariff_type)

            existing = await repository.get_all()
            sort_order = max((row.sort_order for row in existing), default=-1) + 1

            await repository.create(
                {
                    "tariff_type": tariff_type,
                    "price": float(fields["price"]),
                    "days": int(fields["days"]),
                    # By default a tariff covers manual grants up to its own length
                    "max_grant_days": fields.get("max_grant_days", int(fields["days"])),
                    "duration_text": fields["duration_text"],
                    "devices": int(fields["devices"]),
                    "label": fields["label"],
                    "sort_order": sort_order,
                    "is_active": True,
                }
            )

            await TariffService._load_cache(session)

        logger.info(f"Tariff created: {tariff_type} ({fields['price']} RUB, {fields['days']} d)")
        return get_tariff(tariff_type) or {}

    async def update_tariff(self, tariff_type: str, field: str, value: Any) -> dict[str, Any]:
        """Update one field of a tariff and refresh the cache.

        Raises:
            TariffValidationError: If tariff is missing or the price is taken.
        """
        async with async_session_maker() as session:
            repository = TariffRepository(session)

            tariff = await repository.get_by_type(tariff_type)
            if not tariff:
                raise TariffValidationError(f"Тариф {tariff_type} не найден.")

            if field == "price":
                await self._ensure_price_is_free(repository, float(value), tariff_type)

            await repository.update(tariff_type, **{field: value})
            await TariffService._load_cache(session)

        logger.info(f"Tariff updated: {tariff_type}.{field} = {value}")
        return get_tariff(tariff_type) or {}

    async def set_active(self, tariff_type: str, is_active: bool) -> dict[str, Any]:
        """Enable or disable a tariff."""
        return await self.update_tariff(tariff_type, "is_active", is_active)

    async def delete_tariff(self, tariff_type: str) -> bool:
        """Delete a tariff and refresh the cache."""
        async with async_session_maker() as session:
            repository = TariffRepository(session)
            deleted = await repository.delete(tariff_type)
            await TariffService._load_cache(session)

        if deleted:
            logger.info(f"Tariff deleted: {tariff_type}")
        return deleted

    @staticmethod
    async def _ensure_price_is_free(
        repository: TariffRepository, price: float, tariff_type: str
    ) -> None:
        """Check that no other tariff uses the same price.

        Payments without stored tariff metadata are matched by amount, so equal
        prices would make the tariff of such a payment ambiguous.
        """
        for row in await repository.get_all():
            if row.tariff_type != tariff_type and int(row.price) == int(price):
                raise TariffValidationError(
                    f"Цена {int(price)} ₽ уже занята тарифом {row.tariff_type} "
                    f"({row.label}). Цены должны быть уникальными."
                )

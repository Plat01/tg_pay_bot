"""Tariff service with caching."""

import logging
from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import async_session_maker
from src.infrastructure.database.repositories import ProductRepository
from src.models.product import Product

logger = logging.getLogger(__name__)

DEFAULT_PRICES = {
    "monthly": {"price": 199.0, "days": 30},
    "quarterly": {"price": 499.0, "days": 90},
    "yearly": {"price": 1999.0, "days": 365},
}


class TariffService:
    """Service for managing subscription tariffs with caching.

    Cache is updated only:
    - At bot startup (via initialize_cache())
    - When admin calls /prices command
    """

    _instance = None
    _cache: Dict[str, Dict[str, Any]] = {}

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, session: AsyncSession):
        """Initialize service."""
        self.product_repository = ProductRepository(session)

    @classmethod
    async def initialize_cache(cls) -> None:
        """Initialize cache at bot startup (class method, no session needed)."""
        async with async_session_maker() as session:
            product_repository = ProductRepository(session)
            products = await product_repository.get_active_products()

            cls._cache = {}
            for product in products:
                if product.subscription_type in ["monthly", "quarterly", "yearly"]:
                    cls._cache[product.subscription_type] = {
                        "price": product.price,
                        "days": product.duration_days,
                        "label": cls._build_label_static(product),
                        "tariff_type": product.subscription_type,
                        "product_id": product.id,
                    }

            logger.info(f"Tariff cache initialized: {len(cls._cache)} tariffs loaded")

    async def refresh_cache(self) -> None:
        """Refresh cache from database (instance method)."""
        products = await self.product_repository.get_active_products()

        TariffService._cache = {}
        for product in products:
            if product.subscription_type in ["monthly", "quarterly", "yearly"]:
                TariffService._cache[product.subscription_type] = {
                    "price": product.price,
                    "days": product.duration_days,
                    "label": self._build_label(product),
                    "tariff_type": product.subscription_type,
                    "product_id": product.id,
                }

        logger.info(f"Tariff cache refreshed: {len(TariffService._cache)} tariffs loaded")

    @staticmethod
    def _build_label_static(product: Product) -> str:
        """Build display label for tariff (static version)."""
        duration_text = {
            "monthly": "1 месяц",
            "quarterly": "3 месяца",
            "yearly": "12 месяцев",
        }
        duration = duration_text.get(product.subscription_type, f"{product.duration_days} дней")
        return f"{duration} — {int(product.price)} ₽"

    def _build_label(self, product: Product) -> str:
        """Build display label for tariff."""
        duration_text = {
            "monthly": "1 месяц",
            "quarterly": "3 месяца",
            "yearly": "12 месяцев",
        }
        duration = duration_text.get(product.subscription_type, f"{product.duration_days} дней")
        return f"{duration} — {int(product.price)} ₽"

    async def get_tariff_data(self, tariff_type: str) -> Dict[str, Any] | None:
        """Get tariff data by type.

        Returns cached data or default values if not found.
        """
        if tariff_type in TariffService._cache:
            return TariffService._cache[tariff_type]

        if tariff_type in DEFAULT_PRICES:
            default = DEFAULT_PRICES[tariff_type]
            duration_text = {
                "monthly": "1 месяц",
                "quarterly": "3 месяца",
                "yearly": "12 месяцев",
            }
            return {
                "price": default["price"],
                "days": default["days"],
                "label": f"{duration_text[tariff_type]} — {int(default['price'])} ₽",
                "tariff_type": tariff_type,
            }

        return None

    async def get_all_tariffs(self) -> Dict[str, Dict[str, Any]]:
        """Get all tariffs (from cache + defaults)."""
        result = {}

        for tariff_type, default in DEFAULT_PRICES.items():
            duration_text = {
                "monthly": "1 месяц",
                "quarterly": "3 месяца",
                "yearly": "12 месяцев",
            }
            result[tariff_type] = {
                "price": default["price"],
                "days": default["days"],
                "label": f"{duration_text[tariff_type]} — {int(default['price'])} ₽",
                "tariff_type": tariff_type,
            }

        for tariff_type, data in TariffService._cache.items():
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

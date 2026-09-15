"""Repository for TariffSetting model operations."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tariff import TariffSetting


class TariffRepository:
    """Repository for TariffSetting model operations."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session

    async def get_all(self) -> Sequence[TariffSetting]:
        """Get all tariffs ordered for display (shortest term first)."""
        stmt = select(TariffSetting).order_by(TariffSetting.days, TariffSetting.sort_order)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_type(self, tariff_type: str) -> TariffSetting | None:
        """Get tariff by its type code."""
        stmt = select(TariffSetting).where(TariffSetting.tariff_type == tariff_type)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count(self) -> int:
        """Count tariff rows."""
        result = await self.session.execute(select(TariffSetting.id))
        return len(result.scalars().all())

    async def create(self, data: dict[str, Any]) -> TariffSetting:
        """Create a new tariff."""
        tariff = TariffSetting(**data)
        self.session.add(tariff)
        await self.session.commit()
        await self.session.refresh(tariff)
        return tariff

    async def create_many(self, rows: list[dict[str, Any]]) -> None:
        """Create several tariffs in one transaction."""
        for data in rows:
            self.session.add(TariffSetting(**data))
        await self.session.commit()

    async def update(self, tariff_type: str, **fields: Any) -> TariffSetting | None:
        """Update tariff fields by tariff type."""
        tariff = await self.get_by_type(tariff_type)
        if not tariff:
            return None

        for key, value in fields.items():
            setattr(tariff, key, value)
        tariff.updated_at = datetime.now(UTC)

        await self.session.commit()
        await self.session.refresh(tariff)
        return tariff

    async def delete(self, tariff_type: str) -> bool:
        """Delete tariff by type. Returns True if a row was removed."""
        tariff = await self.get_by_type(tariff_type)
        if not tariff:
            return False

        await self.session.delete(tariff)
        await self.session.commit()
        return True

    async def get_by_id(self, tariff_id: uuid.UUID) -> TariffSetting | None:
        """Get tariff by ID."""
        return await self.session.get(TariffSetting, tariff_id)

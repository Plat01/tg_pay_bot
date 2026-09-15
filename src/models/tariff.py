"""Tariff settings model (admin-editable tariffs)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(UTC)


class TariffSetting(SQLModel, table=True):
    """Tariff configuration editable by admins via /tariffs command.

    Defaults are seeded from src.services.tariff.DEFAULT_TARIFFS on first start.
    """

    __tablename__ = "tariff_settings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    tariff_type: str = Field(
        max_length=50,
        unique=True,
        index=True,
        description="Tariff code (trial, monthly, ...), used in callbacks and subscriptions",
    )
    price: float = Field(default=0.0, description="Price in RUB")
    days: int = Field(default=30, description="Subscription duration in days")
    max_grant_days: int | None = Field(
        default=None,
        description="Inclusive upper bound of manual day grants mapped to this tariff",
    )
    duration_text: str = Field(
        max_length=64, default="", description="Duration text shown in buttons and lists"
    )
    devices: int = Field(default=1, description="Device limit for this tariff")
    label: str = Field(max_length=64, default="", description="Russian name of subscription type")
    sort_order: int = Field(default=0, index=True, description="Display order")
    is_active: bool = Field(default=True, index=True, description="Shown to users when true")
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

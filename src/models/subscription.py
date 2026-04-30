"""Subscription model."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.product import Product
    from src.models.encrypted_subscription import EncryptedSubscription

MSK_TZ = ZoneInfo("Europe/Moscow")


def _msk_now() -> datetime:
    """Get current Moscow datetime (UTC+3)."""
    return datetime.now(MSK_TZ)


class Subscription(SQLModel, table=True):
    """Subscription model for user VPN subscriptions."""

    __tablename__ = "subscriptions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    product_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="products.id",
        index=True,
        description="Product ID (nullable after products removal)"
    )
    subscription_type: str | None = Field(
        default=None,
        max_length=50,
        description="Subscription type (trial, monthly, quarterly, yearly)"
    )
    is_active: bool = Field(default=True)
    end_date: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    start_date: datetime = Field(
        default_factory=_msk_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    created_at: datetime = Field(
        default_factory=_msk_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=_msk_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    # Relationships
    user: "User" = Relationship(back_populates="subscriptions")
    product: "Product" = Relationship(back_populates="subscriptions")
    encrypted_subscription: "EncryptedSubscription" = Relationship(
        back_populates="subscription",
        sa_relationship_kwargs={"uselist": False}
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "subscription_type": "monthly",
                "is_active": True,
                "end_date": "2026-05-01T00:00:00Z",
                "start_date": "2026-04-01T00:00:00Z",
            }
        }

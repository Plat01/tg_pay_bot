"""Subscription model."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.product import Product


def _utc_now() -> datetime:
    """Get current UTC datetime (Python 3.12+ compatible)."""
    return datetime.now(timezone.utc)


class Subscription(SQLModel, table=True):
    """Subscription model for user VPN subscriptions."""

    __tablename__ = "subscriptions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    product_id: uuid.UUID = Field(foreign_key="products.id", index=True)
    is_active: bool = Field(default=True)
    end_date: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    start_date: datetime = Field(
        default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    created_at: datetime = Field(
        default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    # Relationships
    user: "User" = Relationship(back_populates="subscriptions")
    product: "Product" = Relationship(back_populates="subscriptions")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "product_id": "123e4567-e89b-12d3-a456-426614174001",
                "is_active": True,
                "end_date": "2026-05-01T00:00:00Z",
                "start_date": "2026-04-01T00:00:00Z",
            }
        }

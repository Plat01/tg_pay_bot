"""Product model for subscription products."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from src.models.subscription import Subscription


def _utc_now() -> datetime:
    """Get current UTC datetime (Python 3.12+ compatible)."""
    return datetime.now(timezone.utc)


class SubscriptionType(str, Enum):
    """Enum for subscription types."""

    TRIAL = "trial"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class Product(SQLModel, table=True):
    """Product model for subscription products that users can purchase."""

    __tablename__ = "products"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    subscription_type: str = Field(sa_column_kwargs={"name": "subscription_type"})
    price: float = Field(default=0.0)
    duration_days: int = Field(default=0)  # Duration in days
    device_limit: int = Field(default=1)
    is_active: bool = Field(default=True)
    happ_link: str = Field(
        max_length=2000
    )  # Link for HAP (Human App Platform?) - increased to accommodate long links
    created_at: datetime = Field(
        default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    # Relationship to subscriptions that use this product
    subscriptions: list["Subscription"] = Relationship(back_populates="product")


class ProductCreate(SQLModel):
    """Schema for creating a product."""

    subscription_type: str
    price: float
    duration_days: int
    device_limit: int
    is_active: bool = True
    happ_link: str


class ProductUpdate(SQLModel):
    """Schema for updating a product."""

    price: float | None = None
    duration_days: int | None = None
    device_limit: int | None = None
    is_active: bool | None = None
    happ_link: str | None = None

"""Payment model."""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import Column, JSON, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from src.models.user import User


def _utc_now() -> datetime:
    """Get current UTC datetime (Python 3.12+ compatible)."""
    return datetime.now(timezone.utc)


class PaymentStatus(str, enum.Enum):
    """Payment status enum."""

    PENDING = "pending"
    COMPLETED = "completed"
    PAID = "paid"  # Alias for COMPLETED
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Payment(SQLModel, table=True):
    """Payment model for tracking user payments."""

    __tablename__ = "payments"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    amount: Decimal = Field(decimal_places=2)
    currency: str = Field(max_length=3, default="RUB")
    status: PaymentStatus = Field(default=PaymentStatus.PENDING)

    # Payment provider info
    payment_provider: str | None = Field(default=None, max_length=50)
    external_id: str | None = Field(default=None, max_length=255, index=True)
    description: str | None = Field(default=None, max_length=500)
    payment_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Timestamps
    created_at: datetime = Field(
        default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=_utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    completed_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    # Relationships
    user: "User" = Relationship(back_populates="payments")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "amount": "1000.00",
                "currency": "RUB",
                "status": "pending",
                "payment_provider": "yookassa",
                "description": "Account top-up",
            }
        }

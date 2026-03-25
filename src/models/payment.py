"""Payment model."""

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from src.models.user import User


class PaymentStatus(str, enum.Enum):
    """Payment status enum."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Payment(SQLModel, table=True):
    """Payment model for tracking user payments."""

    __tablename__ = "payments"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    amount: Decimal = Field(decimal_places=2)
    currency: str = Field(max_length=3, default="RUB")
    status: PaymentStatus = Field(default=PaymentStatus.PENDING)
    
    # Payment provider info
    payment_provider: str | None = Field(default=None, max_length=50)
    external_id: str | None = Field(default=None, max_length=255, index=True)
    description: str | None = Field(default=None, max_length=500)
    payment_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = Field(default=None)

    # Relationships
    user: "User" = Relationship(back_populates="payments")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "user_id": 1,
                "amount": "1000.00",
                "currency": "RUB",
                "status": "pending",
                "payment_provider": "yookassa",
                "description": "Account top-up",
            }
        }
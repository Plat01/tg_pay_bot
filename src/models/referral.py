"""Referral earning model."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.payment import Payment


class ReferralEarningStatus(str, enum.Enum):
    """Referral earning status enum."""

    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"


class ReferralEarning(SQLModel, table=True):
    """Referral earning model for tracking referral rewards."""

    __tablename__ = "referral_earnings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    referrer_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    referral_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    payment_id: uuid.UUID = Field(foreign_key="payments.id", index=True)
    
    # Earning details
    amount: Decimal = Field(decimal_places=2)
    percent: Decimal = Field(decimal_places=2)
    status: ReferralEarningStatus = Field(default=ReferralEarningStatus.PENDING)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: datetime | None = Field(default=None)

    # Relationships
    referrer: "User" = Relationship(
        back_populates="referral_earnings",
        sa_relationship_kwargs={"foreign_keys": "[ReferralEarning.referrer_id]"}
    )
    referral: "User" = Relationship(
        back_populates="earnings_as_referral",
        sa_relationship_kwargs={"foreign_keys": "[ReferralEarning.referral_id]"}
    )
    payment: "Payment" = Relationship()

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "referrer_id": "123e4567-e89b-12d3-a456-426614174000",
                "referral_id": "123e4567-e89b-12d3-a456-426614174001",
                "payment_id": "123e4567-e89b-12d3-a456-426614174002",
                "amount": "100.00",
                "percent": "10.00",
                "status": "pending",
            }
        }
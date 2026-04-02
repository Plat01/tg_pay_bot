"""User model."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from src.models.payment import Payment
    from src.models.referral import ReferralEarning
    from src.models.subscription import Subscription


class User(SQLModel, table=True):
    """User model representing a Telegram user."""

    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    telegram_id: str = Field(unique=True, index=True, max_length=50)
    username: str | None = Field(default=None, max_length=255)
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    language_code: str | None = Field(default=None, max_length=10)
    is_bot: bool = Field(default=False)
    is_premium: bool = Field(default=False)
    
    # Referral fields
    referral_code: str = Field(unique=True, index=True, max_length=20)
    referred_by_id: uuid.UUID | None = Field(default=None, foreign_key="users.id")
    balance: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    payments: list["Payment"] = Relationship(back_populates="user")
    referral_earnings: list["ReferralEarning"] = Relationship(
        back_populates="referrer",
        sa_relationship_kwargs={"foreign_keys": "[ReferralEarning.referrer_id]"}
    )
    earnings_as_referral: list["ReferralEarning"] = Relationship(
        back_populates="referral",
        sa_relationship_kwargs={"foreign_keys": "[ReferralEarning.referral_id]"}
    )
    subscriptions: list["Subscription"] = Relationship(back_populates="user")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "telegram_id": "123456789",
                "username": "johndoe",
                "first_name": "John",
                "last_name": "Doe",
                "language_code": "en",
                "is_bot": False,
                "is_premium": False,
                "referral_code": "ABC12345",
                "balance": "0.00",
            }
        }
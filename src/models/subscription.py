"""Subscription model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from src.models.user import User


class Subscription(SQLModel, table=True):
    """Subscription model for user VPN subscriptions."""

    __tablename__ = "subscriptions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    subscription_type: str = Field(max_length=50)  # trial, monthly, quarterly, yearly
    is_active: bool = Field(default=True)
    device_limit: int = Field(default=1)
    end_date: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: "User" = Relationship(back_populates="subscriptions")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "subscription_type": "monthly",
                "is_active": True,
                "device_limit": 1,
                "end_date": "2026-05-01T00:00:00Z",
            }
        }

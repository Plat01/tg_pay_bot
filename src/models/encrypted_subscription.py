"""Encrypted subscription model for VPN links from sub-oval.online."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import Column, DateTime, JSON
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from src.models.subscription import Subscription


def _utc_now() -> datetime:
    """Get current UTC datetime (Python 3.12+ compatible)."""
    return datetime.now(timezone.utc)


class EncryptedSubscription(SQLModel, table=True):
    """Encrypted subscription model for VPN links.

    Stores encrypted subscription links received from sub-oval.online API.
    Each encrypted subscription is linked to a Subscription record (nullable for trial).
    """

    __tablename__ = "encrypted_subscriptions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    subscription_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="subscriptions.id",
        index=True,
        description="Linked subscription ID (nullable for trial/standalone)"
    )
    public_id: str = Field(max_length=100, index=True, description="Public ID for API access")
    encrypted_link: str = Field(max_length=2000, description="Encrypted subscription link for user")
    vpn_sources_count: int = Field(default=0, description="Number of VPN sources in subscription")
    tags_used: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="Tags used for VPN sources selection"
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="Subscription expiration datetime"
    )
    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="Creation datetime"
    )
    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="Last update datetime"
    )
    metadata_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON),
        description="Original metadata from API (for debugging)"
    )
    behavior_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON),
        description="Original behavior from API (for debugging)"
    )
    ttl_hours: int = Field(default=0, description="Subscription TTL in hours")
    max_devices: int | None = Field(default=None, description="Max devices limit")

    # Relationship to Subscription (nullable for trial)
    subscription: "Subscription | None" = Relationship(
        back_populates="encrypted_subscription"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "subscription_id": "123e4567-e89b-12d3-a456-426614174000",
                "public_id": "abc123xyz",
                "encrypted_link": "https://sub-oval.online/api/v1/subscriptions/abc123xyz",
                "vpn_sources_count": 5,
                "tags_used": ["main"],
                "expires_at": "2026-05-01T00:00:00Z",
                "ttl_hours": 720,
                "max_devices": 3,
            }
        }


class EncryptedSubscriptionCreate(SQLModel):
    """Schema for creating encrypted subscription from API response."""

    id: uuid.UUID
    subscription_id: uuid.UUID | None = None
    public_id: str
    encrypted_link: str
    vpn_sources_count: int
    tags_used: list[str]
    expires_at: datetime
    metadata_json: dict[str, Any] | None = None
    behavior_json: dict[str, Any] | None = None
    ttl_hours: int
    max_devices: int | None = None


class EncryptedSubscriptionUpdate(SQLModel):
    """Schema for updating encrypted subscription."""

    subscription_id: uuid.UUID | None = None
    encrypted_link: str | None = None
    vpn_sources_count: int | None = None
    tags_used: list[str] | None = None
    expires_at: datetime | None = None
    metadata_json: dict[str, Any] | None = None
    behavior_json: dict[str, Any] | None = None
    max_devices: int | None = None
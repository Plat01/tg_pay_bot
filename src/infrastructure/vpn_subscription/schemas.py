"""Pydantic schemas for VPN Subscription API (sub-oval.online).

Based on OpenAPI spec provided by the user.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class VpnTag(str, Enum):
    """Enum for VPN subscription tags."""

    MAIN = "main"
    # Can be extended in future: BACKUP, PREMIUM, etc.


class TrafficInfoRequest(BaseModel):
    """Traffic info for subscription metadata."""

    upload: int = Field(default=0, ge=0, description="Upload traffic in bytes")
    download: int = Field(default=0, ge=0, description="Download traffic in bytes")
    total: int = Field(default=0, ge=0, description="Total traffic limit in bytes")


class InfoBlockRequest(BaseModel):
    """Info block for subscription metadata."""

    color: str = Field(pattern="^(red|blue|green)$", description="Color theme")
    text: str = Field(max_length=200, description="Info block text")
    button_text: str = Field(max_length=25, description="Button text")
    button_link: str = Field(description="Button URL")


class ExpireNotificationRequest(BaseModel):
    """Expire notification settings for subscription metadata."""

    enabled: bool = Field(default=True, description="Enable expire notification")
    button_link: str | None = Field(default=None, description="Button link for notification")


class SubscriptionMetadataRequest(BaseModel):
    """Subscription metadata for HAPP-compatible clients."""

    profile_title: str | None = Field(default=None, max_length=25)
    profile_update_interval: int | None = Field(default=None, ge=1)
    support_url: str | None = Field(default=None)
    profile_web_page_url: str | None = Field(default=None)
    announce: str | None = Field(default=None, max_length=200)
    traffic_info: TrafficInfoRequest | None = Field(default=None)
    info_block: InfoBlockRequest | None = Field(default=None)
    expire_notification: ExpireNotificationRequest | None = Field(default=None)


class SubscriptionBehaviorRequest(BaseModel):
    """Subscription behavior settings for HAPP-compatible clients."""

    autoconnect: bool = Field(default=False, description="Autoconnect on app open")
    autoconnect_type: str = Field(
        default="lastused",
        pattern="^(lastused|lowestdelay)$",
        description="Autoconnect strategy"
    )
    ping_on_open: bool = Field(default=False, description="Ping servers on app open")
    fallback_url: str | None = Field(default=None, description="Fallback subscription URL")


class CreateEncryptedSubscriptionRequest(BaseModel):
    """Request to create encrypted subscription via API."""

    tags: list[str] = Field(min_length=1, description="VPN source tags to include")
    ttl_hours: int = Field(ge=1, le=8760, description="Subscription TTL in hours")
    max_devices: int | None = Field(default=None, ge=1, description="Max devices limit")
    metadata: SubscriptionMetadataRequest | None = Field(default=None)
    behavior: SubscriptionBehaviorRequest | None = Field(default=None)
    provider_id: str | None = Field(default=None)


class EncryptedSubscriptionResponse(BaseModel):
    """Response from encrypted subscription creation API."""

    id: str = Field(description="Internal UUID")
    public_id: str = Field(description="Public ID for subscription URL")
    encrypted_link: str = Field(description="Encrypted subscription link for user")
    expires_at: str = Field(description="Expiration datetime")
    vpn_sources_count: int = Field(description="Number of VPN sources included")
    tags_used: list[str] = Field(description="Tags used for this subscription")
    created_at: str = Field(description="Creation datetime")


class VpnSourceTagResponse(BaseModel):
    """VPN source tag response."""

    id: str = Field(description="Tag UUID")
    name: str = Field(description="Tag name")
    slug: str = Field(description="Tag slug")
    created_at: str = Field(description="Creation datetime")


class VpnSourceDetailResponse(BaseModel):
    """VPN source detail response."""

    id: str = Field(description="VPN source UUID")
    name: str = Field(description="VPN source name")
    uri: str = Field(description="VPN source URI (vless/trojan/etc)")
    description: str | None = Field(default=None)
    is_active: bool = Field(description="Is VPN source active")
    tags: list[VpnSourceTagResponse] = Field(default_factory=list)
    created_at: str = Field(description="Creation datetime")
    updated_at: str = Field(description="Update datetime")


class VpnSourceListResponse(BaseModel):
    """List of VPN sources."""

    items: list[VpnSourceDetailResponse] = Field(default_factory=list)


class TagResponse(BaseModel):
    """Tag response."""

    id: str
    name: str
    slug: str
    created_at: str


class TagListResponse(BaseModel):
    """List of tags."""

    items: list[TagResponse] = Field(default_factory=list)


class SyncTextPreviewItem(BaseModel):
    """Preview item for sync text operation."""

    id: str | None = Field(default=None)
    name: str
    uri: str
    action: str
    tags: list[TagResponse] = Field(default_factory=list)


class SyncTextFailureResponse(BaseModel):
    """Failure response for sync text operation."""

    line: int
    raw: str
    error: str


class SyncTextResponse(BaseModel):
    """Response from sync text operation."""

    dry_run: bool
    mode: str
    import_group: str
    tags: list[str] = Field(default_factory=list)
    parsed_count: int
    valid_count: int
    invalid_count: int
    to_create_count: int
    to_update_count: int
    to_deactivate_count: int
    created: list[SyncTextPreviewItem] = Field(default_factory=list)
    updated: list[SyncTextPreviewItem] = Field(default_factory=list)
    deactivated: list[SyncTextPreviewItem] = Field(default_factory=list)
    failed: list[SyncTextFailureResponse] = Field(default_factory=list)
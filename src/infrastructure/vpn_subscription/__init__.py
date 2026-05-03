"""VPN Subscription API infrastructure package.

Client and schemas for sub-oval.online HAPP-compatible subscription service.
"""

from src.infrastructure.vpn_subscription.client import VpnSubscriptionClient
from src.infrastructure.vpn_subscription.exceptions import (
    VpnSubscriptionApiError,
    VpnSubscriptionAuthError,
    VpnSubscriptionConnectionError,
    VpnSubscriptionError,
    VpnSubscriptionNotFoundError,
    VpnSubscriptionValidationError,
)
from src.infrastructure.vpn_subscription.schemas import (
    CreateEncryptedSubscriptionRequest,
    EncryptedSubscriptionResponse,
    ExpireNotificationRequest,
    InfoBlockRequest,
    SubscriptionBehaviorRequest,
    SubscriptionMetadataRequest,
    TrafficInfoRequest,
    VpnTag,
)

__all__ = [
    "VpnSubscriptionClient",
    "VpnSubscriptionError",
    "VpnSubscriptionConnectionError",
    "VpnSubscriptionAuthError",
    "VpnSubscriptionApiError",
    "VpnSubscriptionNotFoundError",
    "VpnSubscriptionValidationError",
    "CreateEncryptedSubscriptionRequest",
    "EncryptedSubscriptionResponse",
    "SubscriptionMetadataRequest",
    "SubscriptionBehaviorRequest",
    "TrafficInfoRequest",
    "InfoBlockRequest",
    "ExpireNotificationRequest",
    "VpnTag",
]
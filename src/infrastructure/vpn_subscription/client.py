"""Client for VPN Subscription API (sub-oval.online).

HAPP-compatible encrypted subscription link service.
"""

import base64
import logging
from typing import Any

import aiohttp

from src.config import settings
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
    SyncTextResponse,
    TagListResponse,
    VpnSourceListResponse,
)

logger = logging.getLogger(__name__)


class VpnSubscriptionClient:
    """Async client for VPN Subscription API.

    Uses HTTP Basic Auth for admin endpoints.
    """

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize client with configuration.

        Args:
            base_url: API base URL (default from settings).
            username: Admin username (default from settings).
            password: Admin password (default from settings).
            timeout: Request timeout in seconds.
        """
        self.base_url = (base_url or settings.vpn_sub_api_url).rstrip("/")
        self.username = username or settings.vpn_sub_admin_username
        self.password = password or settings.vpn_sub_admin_password
        self.timeout = timeout
        self._session: aiohttp.ClientSession | None = None

    def _get_auth_header(self) -> str:
        """Generate Basic Auth header value."""
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
        return self._session

    async def close(self) -> None:
        """Close aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _request(
        self,
        method: str,
        path: str,
        auth_required: bool = True,
        json_data: dict[str, Any] | None = None,
        text_body: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | str:
        """Make HTTP request to API.

        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            path: API endpoint path
            auth_required: Whether to include Basic Auth header
            json_data: JSON body for request
            text_body: Text body for request (for sync-text endpoint)
            params: Query parameters

        Returns:
            Response data (dict or str)

        Raises:
            VpnSubscriptionConnectionError: Cannot connect to API
            VpnSubscriptionAuthError: Authentication failed
            VpnSubscriptionApiError: API error response
            VpnSubscriptionNotFoundError: Resource not found
            VpnSubscriptionValidationError: Validation error
        """
        session = await self._get_session()
        url = f"{self.base_url}{path}"

        headers = {}
        if auth_required:
            headers["Authorization"] = self._get_auth_header()

        try:
            if text_body:
                headers["Content-Type"] = "text/plain"
                body = text_body
            else:
                body = json_data

            async with session.request(
                method,
                url,
                headers=headers,
                json=body if not text_body else None,
                data=body if text_body else None,
                params=params,
            ) as response:
                if response.status == 204:
                    return {}

                if response.status == 401:
                    raise VpnSubscriptionAuthError(
                        "Authentication failed",
                        details={"status_code": 401},
                    )

                if response.status == 404:
                    raise VpnSubscriptionNotFoundError(
                        "Resource not found",
                        details={"status_code": 404, "url": url},
                    )

                if response.status == 422:
                    body_data = await response.json()
                    raise VpnSubscriptionValidationError(
                        "Validation error",
                        details={"status_code": 422, "errors": body_data},
                    )

                if response.status >= 400:
                    body_data = await response.json()
                    raise VpnSubscriptionApiError(
                        f"API error: {response.status}",
                        status_code=response.status,
                        response_body=body_data,
                    )

                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    return await response.json()
                elif "text/plain" in content_type:
                    return await response.text()
                else:
                    return await response.text()

        except aiohttp.ClientError as e:
            logger.error(f"Connection error to VPN Subscription API: {e}")
            raise VpnSubscriptionConnectionError(
                f"Cannot connect to VPN Subscription API: {e}",
                details={"url": url, "error": str(e)},
            )

    async def health_check(self) -> bool:
        """Check API health status.

        Returns:
            True if API is healthy, False otherwise.
        """
        try:
            await self._request("GET", "/api/v1/health", auth_required=False)
            return True
        except VpnSubscriptionError as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def create_encrypted_subscription(
        self,
        request: CreateEncryptedSubscriptionRequest,
    ) -> EncryptedSubscriptionResponse:
        """Create encrypted subscription via API.

        Args:
            request: Subscription creation request.

        Returns:
            EncryptedSubscriptionResponse with subscription details.

        Raises:
            VpnSubscriptionValidationError: Invalid request data.
            VpnSubscriptionApiError: API error.
        """
        logger.info(
            "Creating encrypted subscription",
            extra={
                "tags": request.tags,
                "ttl_hours": request.ttl_hours,
                "max_devices": request.max_devices,
            },
        )

        response_data = await self._request(
            "POST",
            "/api/v1/admin/subscriptions/encrypted",
            auth_required=True,
            json_data=request.model_dump(exclude_none=True),
        )

        return EncryptedSubscriptionResponse(**response_data)

    async def get_subscription_config(self, public_id: str) -> str:
        """Get subscription config by public ID.

        Args:
            public_id: Public subscription ID.

        Returns:
            Raw subscription config (text/plain).

        Raises:
            VpnSubscriptionNotFoundError: Subscription not found.
        """
        response = await self._request(
            "GET",
            f"/api/v1/subscriptions/{public_id}",
            auth_required=False,
        )

        if isinstance(response, str):
            return response

        raise VpnSubscriptionApiError(
            "Unexpected response format",
            details={"response_type": type(response).__name__},
        )

    async def list_vpn_sources(
        self,
        tags: str | None = None,
        is_active: bool | None = None,
    ) -> VpnSourceListResponse:
        """List VPN sources with optional filters.

        Args:
            tags: Comma-separated tag slugs to filter.
            is_active: Filter by active status.

        Returns:
            VpnSourceListResponse with VPN sources.
        """
        params = {}
        if tags:
            params["tags"] = tags
        if is_active is not None:
            params["is_active"] = str(is_active).lower()

        response_data = await self._request(
            "GET",
            "/api/v1/admin/vpn-sources",
            auth_required=True,
            params=params,
        )

        return VpnSourceListResponse(**response_data)

    async def list_tags(self) -> TagListResponse:
        """List all available tags.

        Returns:
            TagListResponse with all tags.
        """
        response_data = await self._request(
            "GET",
            "/api/v1/admin/vpn-source-tags",
            auth_required=True,
        )

        return TagListResponse(**response_data)

    async def sync_vpn_sources_text(
        self,
        text: str,
        tags: str | None = None,
        import_group: str = "default",
        mode: str = "replace",
        dry_run: bool = True,
        deactivate_missing: bool = True,
        ignore_invalid: bool = False,
        name_strategy: str = "fragment",
    ) -> SyncTextResponse:
        """Sync VPN sources from plain text.

        Args:
            text: VPN sources text (vless/trojan URIs).
            tags: Comma-separated tags for imported sources.
            import_group: Import group name.
            mode: Import mode (replace, upsert, append).
            dry_run: Preview without making changes.
            deactivate_missing: Deactivate sources not in text.
            ignore_invalid: Skip invalid lines instead of failing.
            name_strategy: Name extraction strategy (fragment, host, line_number).

        Returns:
            SyncTextResponse with preview results.
        """
        params = {
            "import_group": import_group,
            "mode": mode,
            "dry_run": str(dry_run).lower(),
            "deactivate_missing": str(deactivate_missing).lower(),
            "ignore_invalid": str(ignore_invalid).lower(),
            "name_strategy": name_strategy,
        }
        if tags:
            params["tags"] = tags

        response_data = await self._request(
            "PUT",
            "/api/v1/admin/vpn-sources/sync-text",
            auth_required=True,
            text_body=text,
            params=params,
        )

        return SyncTextResponse(**response_data)

    async def __aenter__(self) -> "VpnSubscriptionClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - close session."""
        await self.close()
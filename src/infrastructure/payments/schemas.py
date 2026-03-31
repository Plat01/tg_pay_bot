"""Pydantic schemas for Platega API.

This module defines request and response models for the Platega
payment API, providing validation and serialization.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum, IntEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PlategaPaymentMethod(IntEnum):
    """Payment methods available in Platega.

    Each method has a numeric identifier used in API requests.

    Values:
        SBP_QR: СБП QR-код (Russian fast payment system)
        ERIP: ЕРИП (Belarusian payment system)
        CARD_ACQUIRING: Card acquiring (Russian cards)
        INTERNATIONAL: International card payments
        CRYPTO: Cryptocurrency payments
    """

    SBP_QR = 2  # СБП QR-код
    ERIP = 3  # ЕРИП
    CARD_ACQUIRING = 11  # Карточный эквайринг
    INTERNATIONAL = 12  # Международная оплата
    CRYPTO = 13  # Криптовалюта


class PlategaStatus(str, Enum):
    """Payment status in Platega system.

    Values:
        PENDING: Payment created, awaiting completion
        CANCELED: Payment cancelled by user or system
        CONFIRMED: Payment successfully completed
        CHARGEBACKED: Payment reversed (chargeback)
    """

    PENDING = "PENDING"
    CANCELED = "CANCELED"
    CONFIRMED = "CONFIRMED"
    CHARGEBACKED = "CHARGEBACKED"


class PlategaPaymentDetails(BaseModel):
    """Payment amount and currency details.

    Attributes:
        amount: Payment amount in the specified currency.
        currency: Currency code (e.g., 'RUB', 'USD').
    """

    amount: Decimal = Field(..., ge=0, description="Payment amount")
    currency: str = Field(default="RUB", min_length=3, max_length=3, description="Currency code")


class PlategaCreateRequest(BaseModel):
    """Request body for creating a Platega transaction.

    This model represents the payload sent to /transaction/process endpoint.

    Attributes:
        paymentMethod: Numeric payment method identifier.
        paymentDetails: Amount and currency information.
        description: Payment description shown to user.
        return_url: Redirect URL after successful payment.
        failedUrl: Redirect URL after failed payment.
        payload: Custom metadata for tracking.
    """

    paymentMethod: PlategaPaymentMethod = Field(..., description="Payment method number")
    paymentDetails: PlategaPaymentDetails = Field(..., description="Amount and currency")
    description: str = Field(..., min_length=1, max_length=500, description="Payment description")
    return_url: str | None = Field(
        None,
        alias="return",
        description="Redirect URL after success",
    )
    failedUrl: str | None = Field(None, description="Redirect URL after failure")
    payload: str | None = Field(None, description="Custom metadata")

    model_config = {"populate_by_name": True}


class PlategaCreateResponse(BaseModel):
    """Response from Platega transaction creation.

    This model represents the response from /transaction/process endpoint.

    Attributes:
        paymentMethod: Human-readable payment method name.
        transactionId: Unique transaction UUID.
        redirect: URL for completing the payment.
        return_url: Success redirect URL.
        paymentDetails: Amount and currency (string or object).
        status: Initial transaction status.
        expiresIn: Time until expiration (HH:MM:SS format).
        merchantId: Merchant UUID.
        qr: QR code data for SBP payments.
        usdtRate: USDT exchange rate (for crypto payments).
    """

    paymentMethod: str | None = Field(None, description="Payment method name")
    transactionId: UUID = Field(..., description="Transaction UUID")
    redirect: str | None = Field(None, description="Payment URL")
    return_url: str | None = Field(None, alias="return", description="Success redirect URL")
    paymentDetails: PlategaPaymentDetails | str = Field(
        ...,
        description="Payment details",
    )
    status: PlategaStatus = Field(..., description="Transaction status")
    expiresIn: str | None = Field(None, description="Expiration time (HH:MM:SS)")
    merchantId: UUID | None = Field(None, description="Merchant UUID")
    qr: str | None = Field(None, description="QR code data for SBP payments")
    usdtRate: Decimal | None = Field(None, description="USDT exchange rate")

    model_config = {"populate_by_name": True, "extra": "ignore"}

    @field_validator("paymentDetails", mode="before")
    @classmethod
    def parse_payment_details(cls, v: Any) -> PlategaPaymentDetails | str:
        """Parse payment details from string or dict.

        Platega API can return paymentDetails as either a string
        (e.g., "100 RUB") or an object with amount/currency fields.

        Args:
            v: Raw payment details value.

        Returns:
            Parsed PlategaPaymentDetails or original string.
        """
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            return PlategaPaymentDetails(**v)
        return v

    def get_expires_at(self) -> datetime | None:
        """Calculate expiration datetime from expiresIn string.

        Returns:
            Calculated expiration datetime or None if expiresIn is not set.
        """
        if not self.expiresIn:
            return None

        try:
            # Parse HH:MM:SS format
            parts = self.expiresIn.split(":")
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                delta = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                return datetime.now(timezone.utc) + delta
        except (ValueError, AttributeError):
            pass

        return None


class PlategaStatusResponse(BaseModel):
    """Response from Platega status check.

    This model represents the response from /transaction/{id} endpoint.

    Attributes:
        id: Transaction UUID.
        status: Current transaction status.
        paymentDetails: Amount and currency.
        merchantName: Merchant display name.
        merchantId: Merchant UUID.
        comission: Commission amount.
        paymentMethod: Payment method name.
        expiresIn: Remaining time until expiration.
        return_url: Success redirect URL.
        qr: QR code data (for SBP payments).
        payformSuccessUrl: Payment form success URL.
        payload: Custom metadata from creation.
        comissionType: Commission type identifier.
        externalId: External reference ID.
        description: Payment description.
    """

    id: UUID = Field(..., description="Transaction UUID")
    status: PlategaStatus = Field(..., description="Transaction status")
    paymentDetails: PlategaPaymentDetails = Field(..., description="Payment details")
    merchantName: str | None = Field(None, description="Merchant name")
    merchantId: UUID | None = Field(None, description="Merchant UUID")
    comission: Decimal | None = Field(None, description="Commission amount")
    paymentMethod: str | None = Field(None, description="Payment method name")
    expiresIn: str | None = Field(None, description="Expiration time")
    return_url: str | None = Field(None, alias="return", description="Success redirect URL")
    qr: str | None = Field(None, description="QR code data")
    payformSuccessUrl: str | None = Field(None, description="Payment form URL")
    payload: str | None = Field(None, description="Custom metadata")
    comissionType: int | None = Field(None, description="Commission type")
    externalId: str | None = Field(None, description="External reference ID")
    description: str | None = Field(None, description="Payment description")

    model_config = {"populate_by_name": True}

    @field_validator("paymentDetails", mode="before")
    @classmethod
    def parse_payment_details(cls, v: Any) -> PlategaPaymentDetails:
        """Parse payment details from dict.

        Args:
            v: Raw payment details value.

        Returns:
            Parsed PlategaPaymentDetails.

        Raises:
            ValueError: If payment details cannot be parsed.
        """
        if isinstance(v, dict):
            return PlategaPaymentDetails(**v)
        raise ValueError(f"Invalid paymentDetails format: {v}")
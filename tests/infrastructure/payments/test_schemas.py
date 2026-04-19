"""Tests for Platega API schemas.

This module tests Pydantic models for Platega API including:
- Request/response validation
- Field parsing
- Enum values
"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from src.infrastructure.payments.schemas import (
    PlategaCreateRequest,
    PlategaCreateResponse,
    PlategaPaymentDetails,
    PlategaPaymentMethod,
    PlategaStatus,
    PlategaStatusResponse,
)


class TestPlategaPaymentMethod:
    """Tests for PlategaPaymentMethod enum."""

    def test_payment_method_values(self) -> None:
        """Test payment method enum values."""
        assert PlategaPaymentMethod.SBP_QR == 2
        assert PlategaPaymentMethod.ERIP == 3
        assert PlategaPaymentMethod.CARD_ACQUIRING == 11
        assert PlategaPaymentMethod.INTERNATIONAL == 12
        assert PlategaPaymentMethod.CRYPTO == 13

    def test_payment_method_names(self) -> None:
        """Test payment method enum names."""
        assert PlategaPaymentMethod.SBP_QR.name == "SBP_QR"
        assert PlategaPaymentMethod.CARD_ACQUIRING.name == "CARD_ACQUIRING"


class TestPlategaStatus:
    """Tests for PlategaStatus enum."""

    def test_status_values(self) -> None:
        """Test status enum values."""
        assert PlategaStatus.PENDING == "PENDING"
        assert PlategaStatus.CANCELED == "CANCELED"
        assert PlategaStatus.CONFIRMED == "CONFIRMED"
        assert PlategaStatus.CHARGEBACKED == "CHARGEBACKED"


class TestPlategaPaymentDetails:
    """Tests for PlategaPaymentDetails model."""

    def test_valid_payment_details(self) -> None:
        """Test valid payment details creation."""
        details = PlategaPaymentDetails(amount=Decimal("1000.00"), currency="RUB")

        assert details.amount == Decimal("1000.00")
        assert details.currency == "RUB"

    def test_default_currency(self) -> None:
        """Test default currency value."""
        details = PlategaPaymentDetails(amount=Decimal("500.00"))

        assert details.currency == "RUB"

    def test_invalid_amount_negative(self) -> None:
        """Test validation fails for negative amount."""
        with pytest.raises(ValidationError):
            PlategaPaymentDetails(amount=Decimal("-100.00"), currency="RUB")

    def test_invalid_currency_length(self) -> None:
        """Test validation fails for invalid currency length."""
        with pytest.raises(ValidationError):
            PlategaPaymentDetails(amount=Decimal("100.00"), currency="RU")  # Too short

        with pytest.raises(ValidationError):
            PlategaPaymentDetails(amount=Decimal("100.00"), currency="RUBLE")  # Too long


class TestPlategaCreateRequest:
    """Tests for PlategaCreateRequest model."""

    def test_valid_create_request(self) -> None:
        """Test valid create request."""
        request = PlategaCreateRequest(
            paymentMethod=PlategaPaymentMethod.SBP_QR,
            paymentDetails=PlategaPaymentDetails(amount=Decimal("1000.00")),
            description="Test payment",
        )

        assert request.paymentMethod == PlategaPaymentMethod.SBP_QR
        assert request.paymentDetails.amount == Decimal("1000.00")
        assert request.description == "Test payment"

    def test_model_dump_by_alias(self) -> None:
        """Test serialization with aliases."""
        request = PlategaCreateRequest(
            paymentMethod=PlategaPaymentMethod.SBP_QR,
            paymentDetails=PlategaPaymentDetails(amount=Decimal("1000.00")),
            description="Test payment",
            return_url="https://example.com/success",
        )

        data = request.model_dump(by_alias=True)

        # return_url should be serialized as "return" (alias)
        assert "return" in data
        assert data["return"] == "https://example.com/success"

    def test_optional_fields(self) -> None:
        """Test optional fields are None by default."""
        request = PlategaCreateRequest(
            paymentMethod=PlategaPaymentMethod.SBP_QR,
            paymentDetails=PlategaPaymentDetails(amount=Decimal("1000.00")),
            description="Test payment",
        )

        assert request.return_url is None
        assert request.failedUrl is None
        assert request.payload is None

    def test_invalid_description_empty(self) -> None:
        """Test validation fails for empty description."""
        with pytest.raises(ValidationError):
            PlategaCreateRequest(
                paymentMethod=PlategaPaymentMethod.SBP_QR,
                paymentDetails=PlategaPaymentDetails(amount=Decimal("1000.00")),
                description="",  # Empty
            )

    def test_invalid_description_too_long(self) -> None:
        """Test validation fails for too long description."""
        with pytest.raises(ValidationError):
            PlategaCreateRequest(
                paymentMethod=PlategaPaymentMethod.SBP_QR,
                paymentDetails=PlategaPaymentDetails(amount=Decimal("1000.00")),
                description="x" * 501,  # Max is 500
            )


class TestPlategaCreateResponse:
    """Tests for PlategaCreateResponse model."""

    def test_valid_create_response(self) -> None:
        """Test valid create response parsing."""
        response = PlategaCreateResponse(
            transactionId=UUID("550e8400-e29b-41d4-a716-446655440000"),
            redirect="https://pay.platega.io/tx/123",
            paymentDetails={"amount": 1000.00, "currency": "RUB"},
            status=PlategaStatus.PENDING,
            expiresIn="01:00:00",
        )

        assert response.transactionId == UUID("550e8400-e29b-41d4-a716-446655440000")
        assert response.redirect == "https://pay.platega.io/tx/123"
        assert response.status == PlategaStatus.PENDING
        assert response.expiresIn == "01:00:00"

    def test_parse_payment_details_dict(self) -> None:
        """Test parsing paymentDetails from dict."""
        response = PlategaCreateResponse(
            transactionId=UUID("550e8400-e29b-41d4-a716-446655440000"),
            paymentDetails={"amount": 500.00, "currency": "USD"},
            status=PlategaStatus.PENDING,
        )

        assert isinstance(response.paymentDetails, PlategaPaymentDetails)
        assert response.paymentDetails.amount == Decimal("500.00")
        assert response.paymentDetails.currency == "USD"

    def test_parse_payment_details_string(self) -> None:
        """Test parsing paymentDetails from string."""
        response = PlategaCreateResponse(
            transactionId=UUID("550e8400-e29b-41d4-a716-446655440000"),
            paymentDetails="100 RUB",
            status=PlategaStatus.PENDING,
        )

        # Should keep as string
        assert response.paymentDetails == "100 RUB"

    def test_get_expires_at(self) -> None:
        """Test calculating expiration datetime."""
        response = PlategaCreateResponse(
            transactionId=UUID("550e8400-e29b-41d4-a716-446655440000"),
            paymentDetails={"amount": 1000.00, "currency": "RUB"},
            status=PlategaStatus.PENDING,
            expiresIn="01:30:00",
        )

        expires_at = response.get_expires_at()

        assert expires_at is not None
        # Should be approximately 1.5 hours from now
        expected = datetime.now(timezone.utc) + timedelta(hours=1, minutes=30)
        # Allow 1 second tolerance
        assert abs((expires_at - expected).total_seconds()) < 1

    def test_get_expires_at_none(self) -> None:
        """Test get_expires_at when expiresIn is None."""
        response = PlategaCreateResponse(
            transactionId=UUID("550e8400-e29b-41d4-a716-446655440000"),
            paymentDetails={"amount": 1000.00, "currency": "RUB"},
            status=PlategaStatus.PENDING,
        )

        assert response.get_expires_at() is None

    def test_get_expires_at_invalid_format(self) -> None:
        """Test get_expires_at with invalid format."""
        response = PlategaCreateResponse(
            transactionId=UUID("550e8400-e29b-41d4-a716-446655440000"),
            paymentDetails={"amount": 1000.00, "currency": "RUB"},
            status=PlategaStatus.PENDING,
            expiresIn="invalid",
        )

        assert response.get_expires_at() is None


class TestPlategaStatusResponse:
    """Tests for PlategaStatusResponse model."""

    def test_valid_status_response(self) -> None:
        """Test valid status response parsing."""
        response = PlategaStatusResponse(
            id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            status=PlategaStatus.CONFIRMED,
            paymentDetails={"amount": 1000.00, "currency": "RUB"},
            merchantName="Test Merchant",
            description="Account top-up",
        )

        assert response.id == UUID("550e8400-e29b-41d4-a716-446655440000")
        assert response.status == PlategaStatus.CONFIRMED
        assert response.merchantName == "Test Merchant"
        assert response.description == "Account top-up"

    def test_parse_payment_details(self) -> None:
        """Test parsing paymentDetails in status response."""
        response = PlategaStatusResponse(
            id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            status=PlategaStatus.PENDING,
            paymentDetails={"amount": 2500.00, "currency": "RUB"},
        )

        assert isinstance(response.paymentDetails, PlategaPaymentDetails)
        assert response.paymentDetails.amount == Decimal("2500.00")

    def test_invalid_payment_details_format(self) -> None:
        """Test validation fails for invalid paymentDetails."""
        with pytest.raises(ValidationError):
            PlategaStatusResponse(
                id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                status=PlategaStatus.PENDING,
                paymentDetails="invalid string",  # Should be dict
            )

    def test_optional_fields(self) -> None:
        """Test optional fields in status response."""
        response = PlategaStatusResponse(
            id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            status=PlategaStatus.PENDING,
            paymentDetails={"amount": 1000.00, "currency": "RUB"},
        )

        assert response.merchantName is None
        assert response.qr is None
        assert response.payload is None
        assert response.comission is None


class TestSchemaIntegration:
    """Integration tests for schema serialization/deserialization."""

    def test_full_request_response_cycle(self) -> None:
        """Test full cycle of request creation and response parsing."""
        # Create request
        request = PlategaCreateRequest(
            paymentMethod=PlategaPaymentMethod.SBP_QR,
            paymentDetails=PlategaPaymentDetails(amount=Decimal("1500.50")),
            description="Order #12345",
            return_url="https://shop.com/success",
            failedUrl="https://shop.com/fail",
            payload=json.dumps({"order_id": "12345"}),
        )

        # Serialize
        request_data = request.model_dump(by_alias=True)

        # Verify serialization
        assert request_data["paymentMethod"] == 2  # SBP_QR value
        assert "return" in request_data  # Alias used
        assert request_data["paymentDetails"]["amount"] == 1500.50

    def test_response_from_api_data(self) -> None:
        """Test parsing response from realistic API data."""
        api_response = {
            "paymentMethod": "SBP_QR",
            "transactionId": "550e8400-e29b-41d4-a716-446655440000",
            "redirect": "https://pay.platega.io/tx/550e8400",
            "return": "https://shop.com/success",
            "paymentDetails": {"amount": 1500.50, "currency": "RUB"},
            "status": "PENDING",
            "expiresIn": "00:45:00",
            "merchantId": "550e8400-e29b-41d4-a716-446655440001",
            "qr": "https://qr.platega.io/550e8400",
        }

        response = PlategaCreateResponse(**api_response)

        assert response.transactionId == UUID("550e8400-e29b-41d4-a716-446655440000")
        assert response.status == PlategaStatus.PENDING
        assert response.paymentDetails.amount == Decimal("1500.50")
        assert response.qr == "https://qr.platega.io/550e8400"
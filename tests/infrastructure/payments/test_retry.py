"""Tests for retry logic with exponential backoff.

This module tests the retry decorator and RetryConfig including:
- Retry behavior on failures
- Exponential backoff calculation
- Timeout handling
- Exception handling
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from src.infrastructure.payments.exceptions import (
    PaymentProviderUnavailable,
    PaymentTimeoutError,
)
from src.infrastructure.payments.retry import RetryConfig, with_retry


class TestWithRetryDecorator:
    """Tests for with_retry decorator."""

    @pytest.mark.asyncio
    async def test_success_no_retry(self) -> None:
        """Test successful function doesn't retry."""
        calls = [0]  # Use list to allow modification in nested function

        @with_retry(max_retries=3)
        async def successful_func() -> str:
            calls[0] += 1
            return "success"

        result = await successful_func()

        assert result == "success"
        assert calls[0] == 1  # Only called once

    @pytest.mark.asyncio
    async def test_retry_on_client_error(self) -> None:
        """Test retry on aiohttp.ClientError."""
        calls = [0]

        @with_retry(max_retries=2, base_delay=0.1)
        async def failing_func() -> str:
            calls[0] += 1
            if calls[0] < 3:
                raise aiohttp.ClientError("Connection failed")
            return "success"

        result = await failing_func()

        assert result == "success"
        assert calls[0] == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_retry_exhausted(self) -> None:
        """Test exception raised after retries exhausted."""
        calls = [0]

        @with_retry(max_retries=2, base_delay=0.1)
        async def always_failing_func() -> str:
            calls[0] += 1
            raise aiohttp.ClientError("Always fails")

        with pytest.raises(PaymentProviderUnavailable) as exc_info:
            await always_failing_func()

        assert calls[0] == 3  # Initial + 2 retries
        assert exc_info.value.retry_count == 2
        assert "Provider unavailable after 2 retries" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_handling(self) -> None:
        """Test timeout error handling."""
        calls = [0]

        @with_retry(max_retries=1, base_delay=0.1, timeout=0.5)
        async def slow_func() -> str:
            calls[0] += 1
            await asyncio.sleep(1.0)  # Sleep longer than timeout
            return "success"

        with pytest.raises(PaymentTimeoutError) as exc_info:
            await slow_func()

        assert exc_info.value.timeout_seconds == 0.5

    @pytest.mark.asyncio
    async def test_custom_exceptions(self) -> None:
        """Test retry on custom exception types."""
        calls = [0]

        class CustomError(Exception):
            pass

        @with_retry(max_retries=2, base_delay=0.1, exceptions=(CustomError,))
        async def custom_failing_func() -> str:
            calls[0] += 1
            if calls[0] < 3:
                raise CustomError("Custom error")
            return "success"

        result = await custom_failing_func()

        assert result == "success"
        assert calls[0] == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_unexpected_exception(self) -> None:
        """Test no retry on unexpected exception type."""
        calls = [0]

        class UnexpectedError(Exception):
            pass

        @with_retry(max_retries=3, base_delay=0.1)
        async def unexpected_failing_func() -> str:
            calls[0] += 1
            raise UnexpectedError("Unexpected error")

        with pytest.raises(UnexpectedError):
            await unexpected_failing_func()

        assert calls[0] == 1  # No retries for unexpected exception

    @pytest.mark.asyncio
    async def test_exponential_backoff(self) -> None:
        """Test exponential backoff delays."""
        delays = []

        @with_retry(max_retries=3, base_delay=1.0, exponential_base=2.0)
        async def tracking_func() -> str:
            raise aiohttp.ClientError("Always fails")

        # Patch asyncio.sleep to track delays
        original_sleep = asyncio.sleep

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)
            # Don't actually sleep in tests

        with patch("asyncio.sleep", mock_sleep):
            with pytest.raises(PaymentProviderUnavailable):
                await tracking_func()

        # Check exponential backoff: 1.0, 2.0, 4.0 (capped at max_delay)
        assert len(delays) == 3
        assert delays[0] == 1.0  # base_delay * 2^0
        assert delays[1] == 2.0  # base_delay * 2^1
        assert delays[2] == 4.0  # base_delay * 2^2

    @pytest.mark.asyncio
    async def test_max_delay_cap(self) -> None:
        """Test that delay is capped at max_delay."""
        delays = []

        @with_retry(max_retries=5, base_delay=1.0, max_delay=5.0, exponential_base=2.0)
        async def tracking_func() -> str:
            raise aiohttp.ClientError("Always fails")

        async def mock_sleep(delay: float) -> None:
            delays.append(delay)

        with patch("asyncio.sleep", mock_sleep):
            with pytest.raises(PaymentProviderUnavailable):
                await tracking_func()

        # All delays should be capped at 5.0
        for delay in delays:
            assert delay <= 5.0


class TestRetryConfig:
    """Tests for RetryConfig class."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0
        assert config.exponential_base == 2.0
        assert config.timeout is None

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=10.0,
            exponential_base=3.0,
            timeout=15.0,
        )

        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 10.0
        assert config.exponential_base == 3.0
        assert config.timeout == 15.0

    @pytest.mark.asyncio
    async def test_get_decorator(self) -> None:
        """Test getting decorator from config."""
        config = RetryConfig(max_retries=2, base_delay=0.1)
        decorator = config.get_decorator()

        # Decorator should be callable
        assert callable(decorator)

        # Test it works
        calls = [0]

        @decorator
        async def test_func() -> str:
            calls[0] += 1
            if calls[0] < 2:
                raise aiohttp.ClientError("Fail")
            return "ok"

        result = await test_func()
        assert result == "ok"
        assert calls[0] == 2

    @pytest.mark.asyncio
    async def test_get_decorator_with_custom_exceptions(self) -> None:
        """Test getting decorator with custom exceptions."""
        config = RetryConfig(max_retries=1, base_delay=0.1)

        class CustomError(Exception):
            pass

        decorator = config.get_decorator(exceptions=(CustomError,))

        calls = [0]

        @decorator
        async def test_func() -> str:
            calls[0] += 1
            if calls[0] < 2:
                raise CustomError("Fail")
            return "ok"

        result = await test_func()
        assert result == "ok"


class TestDefaultRetryConfig:
    """Tests for DEFAULT_RETRY_CONFIG."""

    def test_default_config_exists(self) -> None:
        """Test that DEFAULT_RETRY_CONFIG is defined."""
        from src.infrastructure.payments.retry import DEFAULT_RETRY_CONFIG

        assert DEFAULT_RETRY_CONFIG is not None
        assert isinstance(DEFAULT_RETRY_CONFIG, RetryConfig)

    def test_default_config_values(self) -> None:
        """Test DEFAULT_RETRY_CONFIG values."""
        from src.infrastructure.payments.retry import DEFAULT_RETRY_CONFIG

        assert DEFAULT_RETRY_CONFIG.max_retries == 3
        assert DEFAULT_RETRY_CONFIG.base_delay == 1.0
        assert DEFAULT_RETRY_CONFIG.max_delay == 30.0
        assert DEFAULT_RETRY_CONFIG.exponential_base == 2.0
        assert DEFAULT_RETRY_CONFIG.timeout == 10.0
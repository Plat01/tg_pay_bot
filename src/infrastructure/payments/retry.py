"""Retry logic with exponential backoff for payment API requests.

This module provides a decorator for automatic retry of failed
API requests with configurable exponential backoff strategy.
"""

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

import aiohttp

from src.infrastructure.payments.exceptions import PaymentProviderUnavailable, PaymentTimeoutError

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (aiohttp.ClientError,),
    timeout: float | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for retry with exponential backoff.

    This decorator wraps async functions to automatically retry
    on specified exceptions, with exponentially increasing delays
    between attempts.

    Args:
        max_retries: Maximum number of retry attempts (default: 3).
        base_delay: Initial delay in seconds (default: 1.0).
        max_delay: Maximum delay cap in seconds (default: 30.0).
        exponential_base: Multiplier for each retry (default: 2.0).
        exceptions: Exception types to retry on (default: aiohttp.ClientError).
        timeout: Request timeout in seconds (optional).

    Returns:
        Decorated function with retry logic.

    Example:
        >>> @with_retry(max_retries=3, base_delay=1.0)
        ... async def fetch_data():
        ...     return await api_client.get("/data")

    Note:
        The decorated function will raise PaymentProviderUnavailable
        after all retries are exhausted.
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    # Execute the function with optional timeout
                    if timeout:
                        return await asyncio.wait_for(
                            func(*args, **kwargs),
                            timeout=timeout,
                        )
                    else:
                        return await func(*args, **kwargs)

                except asyncio.TimeoutError as e:
                    # Handle timeout separately
                    last_exception = PaymentTimeoutError(
                        message="API request timed out",
                        timeout_seconds=timeout,
                    )
                    logger.warning(
                        f"Timeout on attempt {attempt + 1}/{max_retries + 1}: "
                        f"function {func.__name__}"
                    )

                except exceptions as e:
                    last_exception = e
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{max_retries + 1} "
                        f"for {func.__name__}: {type(e).__name__}: {e}"
                    )

                # Check if we've exhausted retries
                if attempt == max_retries:
                    if isinstance(last_exception, PaymentTimeoutError):
                        raise last_exception
                    raise PaymentProviderUnavailable(
                        message=f"Provider unavailable after {max_retries} retries",
                        retry_count=max_retries,
                        details={"last_error": str(last_exception)},
                    ) from last_exception

                # Calculate delay with exponential backoff
                delay = min(
                    base_delay * (exponential_base ** attempt),
                    max_delay,
                )

                logger.info(
                    f"Waiting {delay:.1f}s before retry "
                    f"(attempt {attempt + 2}/{max_retries + 1})"
                )

                await asyncio.sleep(delay)

            # This should never be reached, but satisfies type checker
            raise PaymentProviderUnavailable("Unexpected retry loop exit")

        return wrapper

    return decorator


class RetryConfig:
    """Configuration for retry behavior.

    This class encapsulates retry settings and can be used
    to create consistent retry decorators across the application.

    Attributes:
        max_retries: Maximum retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay cap.
        exponential_base: Exponential multiplier.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        timeout: float | None = None,
    ) -> None:
        """Initialize retry configuration.

        Args:
            max_retries: Maximum retry attempts.
            base_delay: Initial delay in seconds.
            max_delay: Maximum delay cap.
            exponential_base: Exponential multiplier.
            timeout: Request timeout in seconds.
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.timeout = timeout

    def get_decorator(
        self,
        exceptions: tuple[type[Exception], ...] = (aiohttp.ClientError,),
    ) -> Callable[[Callable[P, T]], Callable[P, T]]:
        """Get retry decorator with this configuration.

        Args:
            exceptions: Exception types to retry on.

        Returns:
            Configured retry decorator.
        """
        return with_retry(
            max_retries=self.max_retries,
            base_delay=self.base_delay,
            max_delay=self.max_delay,
            exponential_base=self.exponential_base,
            exceptions=exceptions,
            timeout=self.timeout,
        )


# Default retry configuration for payment providers
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    timeout=10.0,
)
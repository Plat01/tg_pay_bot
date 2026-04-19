"""User service for business logic."""

import random
import string
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.infrastructure.database.repositories import UserRepository
from src.models.user import User


class UserService:
    """Service for user-related business logic."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize user service with session."""
        self.repository = UserRepository(session)

    def _generate_referral_code(self) -> str:
        """Generate a unique referral code."""
        length = settings.referral_code_length
        chars = string.ascii_uppercase + string.digits
        return "".join(random.choices(chars, k=length))

    async def get_or_create_user(
        self,
        telegram_id: int | str,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
        is_bot: bool = False,
        is_premium: bool = False,
        referral_code: str | None = None,
    ) -> User:
        """Get existing user or create a new one."""
        # Convert telegram_id to string for storage
        telegram_id_str = str(telegram_id)
        user = await self.repository.get_by_telegram_id(telegram_id_str)

        if user:
            # Update user info if changed
            update_data = {}
            if user.username != username:
                update_data["username"] = username
            if user.first_name != first_name:
                update_data["first_name"] = first_name
            if user.last_name != last_name:
                update_data["last_name"] = last_name
            if user.language_code != language_code:
                update_data["language_code"] = language_code
            if user.is_premium != is_premium:
                update_data["is_premium"] = is_premium

            if update_data:
                update_data["updated_at"] = datetime.now(timezone.utc)
                user = await self.repository.update(user, update_data)
            return user

        # Create new user
        user_data = {
            "telegram_id": telegram_id_str,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "language_code": language_code,
            "is_bot": is_bot,
            "is_premium": is_premium,
            "referral_code": self._generate_referral_code(),
        }

        # Handle referral
        if referral_code:
            referrer = await self.repository.get_by_referral_code(referral_code)
            if referrer:
                user_data["referred_by_id"] = referrer.id

        try:
            return await self.repository.create(user_data)
        except IntegrityError:
            # Race condition: another request already created this user
            await self.session.rollback()
            user = await self.repository.get_by_telegram_id(telegram_id_str)
            if user:
                return user
            raise

    async def get_user_by_telegram_id(self, telegram_id: int | str) -> User | None:
        """Get user by Telegram ID."""
        return await self.repository.get_by_telegram_id(str(telegram_id))

    async def get_user_by_referral_code(self, referral_code: str) -> User | None:
        """Get user by referral code."""
        return await self.repository.get_by_referral_code(referral_code)

    async def get_referrals(self, user_id: uuid.UUID) -> list[User]:
        """Get all users referred by this user."""
        return await self.repository.get_referrals(user_id)

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Get user by internal ID."""
        return await self.repository.get_by_id(user_id)

    async def update_balance(self, user: User, amount: Decimal) -> User:
        """Update user balance.

        Args:
            user: User instance.
            amount: Amount to add (can be negative for deductions).

        Returns:
            Updated User instance.
        """
        new_balance = user.balance + amount
        user = await self.repository.update(user, {"balance": new_balance})
        return user

    async def mark_trial_used(self, user: User) -> User:
        """Mark user as having used trial period.

        Args:
            user: User instance.

        Returns:
            Updated User instance with is_new=False.
        """
        user = await self.repository.update(user, {"is_new": False})
        return user

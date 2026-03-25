"""User service for business logic."""

import random
import string
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.user import User
from src.repositories.user import UserRepository


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
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
        is_bot: bool = False,
        is_premium: bool = False,
        referral_code: str | None = None,
    ) -> User:
        """Get existing user or create a new one."""
        user = await self.repository.get_by_telegram_id(telegram_id)

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
                update_data["updated_at"] = datetime.utcnow()
                user = await self.repository.update(user, update_data)
            return user

        # Create new user
        user_data = {
            "telegram_id": telegram_id,
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

        return await self.repository.create(user_data)

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        """Get user by Telegram ID."""
        return await self.repository.get_by_telegram_id(telegram_id)

    async def get_user_by_referral_code(self, referral_code: str) -> User | None:
        """Get user by referral code."""
        return await self.repository.get_by_referral_code(referral_code)

    async def get_referrals(self, user_id: int) -> list[User]:
        """Get all users referred by this user."""
        return await self.repository.get_referrals(user_id)
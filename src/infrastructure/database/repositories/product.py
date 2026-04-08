"""Repository for Product model operations."""

import uuid
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.models.product import Product


class ProductRepository:
    """Repository for Product model operations."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session

    async def get_product_by_id(self, product_id: uuid.UUID) -> Product | None:
        """Get product by ID."""
        stmt = select(Product).where(Product.id == product_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_product_by_subscription_type(self, subscription_type: str) -> Product | None:
        """Get product by subscription type."""
        stmt = select(Product).where(Product.subscription_type == subscription_type)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_products(self) -> Sequence[Product]:
        """Get all products."""
        stmt = select(Product)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_active_products(self) -> Sequence[Product]:
        """Get all active products."""
        stmt = select(Product).where(Product.is_active.is_(True))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_product(self, product: Product) -> Product:
        """Create a new product."""
        self.session.add(product)
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def update_product(self, product_id: uuid.UUID, **kwargs) -> Product | None:
        """Update product fields."""
        product = await self.get_product_by_id(product_id)
        if not product:
            return None

        for key, value in kwargs.items():
            setattr(product, key, value)

        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def delete_product(self, product_id: uuid.UUID) -> bool:
        """Delete product by ID."""
        product = await self.get_product_by_id(product_id)
        if not product:
            return False

        await self.session.delete(product)
        await self.session.commit()
        return True

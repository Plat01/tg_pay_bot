"""Base repository with common CRUD operations."""

from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select

ModelType = TypeVar("ModelType", bound=SQLModel)


class BaseRepository(Generic[ModelType]):
    """Base repository with common database operations."""

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        """Initialize repository with model and session."""
        self.model = model
        self.session = session

    async def create(self, data: dict) -> ModelType:
        """Create a new record."""
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def get_by_id(self, id: int) -> ModelType | None:
        """Get record by ID."""
        return await self.session.get(self.model, id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """Get all records with pagination."""
        statement = select(self.model).offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def update(self, instance: ModelType, data: dict) -> ModelType:
        """Update an existing record.
        
        Note: None values are filtered out to prevent violating NOT NULL constraints.
        """
        for key, value in data.items():
            # Skip None values to avoid setting NULL on NOT NULL columns
            if value is not None:
                setattr(instance, key, value)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def delete(self, instance: ModelType) -> None:
        """Delete a record."""
        await self.session.delete(instance)
        await self.session.commit()
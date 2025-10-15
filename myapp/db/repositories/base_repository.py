# repositories/base_repository.py
from typing import TypeVar, Generic, Type, Optional, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.models import HasId  

T = TypeVar("T", bound=HasId)

class BaseRepository(Generic[T]):
    def __init__(self, db: AsyncSession, model: Type[T]):
        self.db = db
        self.model = model

    async def get_by_id(self, obj_id: int) -> Optional[T]:
        result = await self.db.execute(select(self.model).where(self.model.id == obj_id))
        return result.scalar_one_or_none()

    async def list_all(self) -> Sequence[T]:
        result = await self.db.execute(select(self.model))
        return result.scalars().all()

    async def create(self, obj: T) -> T:
        
            self.db.add(obj)
            return obj

    async def delete(self, obj: T) -> None:
        
            await self.db.delete(obj)


from typing import Optional, Dict, Any, Protocol, List
from pydantic import BaseModel

# 2. Pydantic Models (Data Validation)
class LocationParams(BaseModel):
    latitude: float
    longitude: float
    place: str

class BookingState(BaseModel):
    pickup_location: Optional[str] = None
    destination: Optional[str] = None
    pickup_time: Optional[str] = None 
    special_requests: Optional[str] = None
    confirmed: bool = False



class BookingStateRepository(Protocol):

    async def get_state(self) -> BookingState:
        ...

    async def is_complete(self) -> bool:
        ...

    async def summary(self) -> str:
        ...

    async def confirm(self)->bool:
        ...

    async def is_confirm(self) -> bool: 
        ...

    async def update(self, data: Dict[str, Any]) -> bool:
        ...
    
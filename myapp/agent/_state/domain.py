from typing import Optional, Dict, Any, Protocol, List
from pydantic import BaseModel
from datetime import datetime

# 2. Pydantic Models (Data Validation)
class LocationParams(BaseModel):
    latitude: float
    longitude: float
    place: str

class PickupParams(BaseModel):
    type: str
    target_time_iso: datetime
    

class BookingState(BaseModel):
    pickup_location: Optional[str] | Optional[LocationParams] = None
    destination: Optional[str] | Optional[LocationParams] = None
    pickup_time: Optional[str] | Optional[PickupParams] = None 
    special_requests: Optional[str] = None
    confirmed: bool = False

class InputData(BaseModel):
      input: str
      channel: Optional[str] = "WHATSAPP"
      user_id: str 

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
    
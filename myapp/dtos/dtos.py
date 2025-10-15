from typing import TypedDict, Optional, List

class driverDto(TypedDict):
    channel_id: str
    channel: str
    docs: Optional[List[str]]
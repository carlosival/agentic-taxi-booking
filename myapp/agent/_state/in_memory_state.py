from . import BookingState
from typing import Dict, Any

class InMemoryState:

    def __init__(self):

        self.booking_state = BookingState()

    
    def get_state(self) -> BookingState:

        return self.booking_state


    def is_complete(self) -> bool:
        """Check if the booking has all necessary info to proceed."""
        return all([
            self.booking_state.pickup_location,
            self.booking_state.destination,
            self.booking_state.pickup_time,
            self.booking_state.passengers is not None
        ])

    def summary(self) -> str:
        """Generate a human-readable summary of the booking."""
        return (
            f"Pickup: {self.booking_state.pickup_location or 'N/A'}, "
            f"Destination: {self.booking_state.destination or 'N/A'}, "
            f"Time: {self.booking_state.pickup_time or 'N/A'}, "
            f"Passengers: {self.booking_state.passengers if self.booking_state.passengers is not None else 'N/A'}, "
            f"Requests: {self.booking_state.special_requests or 'None'}, "
            f"Confirmed: {'Yes' if self.booking_state.confirmed else 'No'}"
        )

    def confirm(self):
        """Set the booking as confirmed if complete."""
        if self.is_complete():
            self.booking_state.confirmed = True
        else:
            raise ValueError("Cannot confirm booking: missing required information.")

    def is_confirm(self) -> bool: 

        return self.is_complete() and self.booking_state.confirmed

    def update(self, data: Dict[str, Any]):
        print(data)
        assert isinstance(data,Dict) , f"data is {type(data)}, type Dict expected"
        
        """Update the booking state with partial or full data from a dict."""
        for key, value in data.items():
            if hasattr(self.booking_state, key):
                setattr(self.booking_state, key, value)
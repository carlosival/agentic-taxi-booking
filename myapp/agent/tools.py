import datetime
from zoneinfo import ZoneInfo
import uuid
from ._tool import Tool

END = None



class FinalizeBookingTool(Tool):
    def name(self):
        return "finalize_booking"
    def description(self):
        return "Use this tool after the user successfully confirms the taxi booking."
    def use(self):
        confirmation_id = str(uuid.uuid4())[:8]  # Shortened UUID for simplicity
        now = datetime.datetime.now(ZoneInfo("UTC")).astimezone()
        time_str = now.strftime("%Y-%m-%d %H:%M:%S %Z")

        return (
            f"✅ Booking confirmed!\n"
            f"📄 Confirmation ID: {confirmation_id}\n"
            f"🕒 Time: {time_str}\n"
            f"A driver will contact you shortly with further details."
        )


class UpdateBookingTool(Tool):
    def name(self):
        return "update_booking_state"
    def description(self):
        return "Use this tool to update new booking details"
    def use(self):
        return "Update State"



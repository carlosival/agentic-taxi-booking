from sqlalchemy import (
    
    DateTime,
    ForeignKey,
    Enum as SQLAEnum,
    func,
)
from sqlalchemy.orm import (
    declarative_base,
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.dialects.postgresql import UUID
from enum import Enum as PyEnum
import uuid
from typing import Protocol, Optional, List


Base = declarative_base()

# ---- Protocol ----
class HasId(Protocol):
    id: Mapped[int]

# ---- Enums ----
class BookingStatus(str, PyEnum):
    pending = "pending"
    confirmed = "confirmed"
    failed = "failed"
    successful = "successful"

class ReplyStatus(str, PyEnum):
    pending = "pending"
    confirmed = "confirmed"
    reply = "reply"
    out_date = "out_date"
    successful = "successful"

class MessageRole(str, PyEnum):
    user = "user"
    ai = "ai"
    system = "system"

# ---- Models ----
class Driver(Base):
    __tablename__ = "driver"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=True)
    rank: Mapped[int] = mapped_column(default=0)
    channel: Mapped[str] = mapped_column(default="WHATSAPP")
    channel_id: Mapped[str] = mapped_column(unique=True, nullable=False)
    carnet: Mapped[Optional[str]] = mapped_column(nullable=True)
    licencia: Mapped[Optional[str]] = mapped_column(nullable=True)
    matricula: Mapped[Optional[str]] = mapped_column(nullable=True)
    email: Mapped[Optional[str]] = mapped_column(nullable=True)
    active: Mapped[bool] = mapped_column(default=True)
    city: Mapped[str] = mapped_column(default="HABANA")

    bookings: Mapped[List["Booking"]] = relationship(back_populates="driver")
    notifications: Mapped[List["Notification"]] = relationship(back_populates="driver")


class Booking(Base):
    __tablename__ = "booking"

    id: Mapped[int] = mapped_column(primary_key=True)
    driver_id: Mapped[Optional[int]] = mapped_column(ForeignKey("driver.id"))
    status: Mapped[BookingStatus] = mapped_column(
        SQLAEnum(BookingStatus, create_constraint=True), 
        default=BookingStatus.pending, 
        nullable=False
    )
    customer_channel: Mapped[str] = mapped_column(default="WHATSAPP")
    customer_channel_id: Mapped[str] = mapped_column()
    pickup_location: Mapped[str] = mapped_column()
    destination: Mapped[str] = mapped_column()
    pickup_time: Mapped[str] = mapped_column()
    passengers: Mapped[int] = mapped_column(default=1)
    special_requests: Mapped[str] = mapped_column(nullable=True)
    timestamp_created: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.timezone('utc', func.now()))
    timestamp_confirmed: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)
    identifier: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4)

    driver: Mapped[Optional["Driver"]] = relationship(back_populates="bookings")
    notifications: Mapped[List["Notification"]] = relationship(back_populates="booking")


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("driver.id"))
    booking_id: Mapped[int] = mapped_column(ForeignKey("booking.id"))
    timestamp_created: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.timezone('utc', func.now()))
    channel_send: Mapped[str] = mapped_column(default="WHATSAPP")
    message_send_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4)
    reply_status: Mapped[ReplyStatus] = mapped_column(SQLAEnum(ReplyStatus), default=ReplyStatus.pending)

    booking: Mapped["Booking"] = relationship(back_populates="notifications")
    driver: Mapped["Driver"] = relationship(back_populates="notifications")



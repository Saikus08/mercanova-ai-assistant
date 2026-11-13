"""Order value objects shared by the domain and the persistence constraints."""

from enum import StrEnum


class OrderStatus(StrEnum):
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class DeliveryMethod(StrEnum):
    PICKUP = "pickup"
    SHIPPING = "shipping"

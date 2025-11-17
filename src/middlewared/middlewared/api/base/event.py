from dataclasses import dataclass
from typing import Literal

from .model import BaseModel


@dataclass(slots=True, frozen=True, kw_only=True)
class Event:
    """
    Represents a middleware API event
    """

    # event name
    name: str
    # event description
    description: str
    # list of roles than can subscribe to event
    roles: list[str] | None
    # data models for different event types (ADDED, CHANGED, REMOVED)
    models: dict[Literal["ADDED", "CHANGED", "REMOVED"], type[BaseModel]]
    # Subscribing to this event requires authentication
    authentication_required: bool = True
    # Subscribing to this event requires authorization. This is incompatible with `roles`
    authorization_required: bool = True
    # whether this event is private
    private: bool = False

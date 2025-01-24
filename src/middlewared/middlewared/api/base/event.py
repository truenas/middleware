from dataclasses import dataclass

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
    roles: list[str]
    # data models for different event types (ADDED, CHANGED, REMOVED)
    models: dict[str, type[BaseModel]]
    # whether this event is private
    private: bool = False

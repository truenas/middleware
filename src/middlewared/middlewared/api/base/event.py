from .model import BaseModel


class Event:
    """
    Represents a middleware API event
    """

    def __init__(self, name: str, description: str, roles: list[str], models: dict[str, type[BaseModel]],
                 private: bool = False):
        """
        :param name: event name
        :param description: event description
        :param roles: list of roles than can subscribe to event
        :param models: data models for different event types (ADDED, CHANGED, REMOVED)
        :param private: whether this event is private
        """
        self.name = name
        self.description = description
        self.roles = roles
        self.models = models
        self.private = private

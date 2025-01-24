from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from middlewared.main import Middleware


class Event:
    """
    Represents a middleware API event used in JSON-RPC server.
    """

    def __init__(self, middleware: "Middleware", name: str):
        """
        :param middleware: `Middleware` instance
        :param name: event name
        """
        self.middleware = middleware
        self.name = name
        self.event = self.middleware.events.get_event(self.name)

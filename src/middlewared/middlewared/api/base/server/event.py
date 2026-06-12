from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from middlewared.main import Middleware


class Event:
    """
    Represents a middleware API event used in JSON-RPC server.
    """

    def __init__(self, middleware: "Middleware", name: str, event: dict[str, Any]):
        """
        :param middleware: `Middleware` instance
        :param name: event name
        :param event: event description
        """
        self.middleware = middleware
        self.name = name
        self.event = event

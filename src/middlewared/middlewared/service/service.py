from typing import TYPE_CHECKING

from middlewared.logger import Logger
if TYPE_CHECKING:
    from middlewared.main import Middleware

from .base import ServiceBase


class Service(object, metaclass=ServiceBase):
    """
    Generic service abstract class

    This is meant for services that do not follow any standard.
    """
    def __init__(self, middleware: "Middleware"):
        self.logger = Logger(type(self).__name__).getLogger()
        self.middleware = middleware

        for event in self._config.events:
            self.middleware.event_register(
                event.name,
                event.description,
                private=event.private,
                models=event.models,
                roles=event.roles,
            )

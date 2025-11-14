from typing import TYPE_CHECKING

from middlewared.logger import Logger
if TYPE_CHECKING:
    from middlewared.main import Middleware

from .base import ServiceBase


class Service(metaclass=ServiceBase):
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
                no_auth_required=not event.authentication_required,
                no_authz_required=not event.authorization_required,
                roles=event.roles,
            )

        for name, klass in self._config.event_sources.items():
            self.middleware.event_source_manager.register(name, klass)

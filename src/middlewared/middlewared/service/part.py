from __future__ import annotations

from .context import ServiceContext

__all__ = ("ServicePart",)


class ServicePart(ServiceContext):
    def __init__(self, context: ServiceContext):
        super().__init__(context.middleware, context.logger)

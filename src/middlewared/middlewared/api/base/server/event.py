from typing import Annotated, TYPE_CHECKING

from pydantic import BaseModel, Field, create_model

from middlewared.api.base.handler.version import APIVersionDoesNotContainModelException, APIVersionsAdapter

if TYPE_CHECKING:
    from middlewared.main import Middleware


class Event:
    """
    Represents a middleware API event used in JSON-RPC server.
    """

    def __init__(self, middleware: "Middleware", name: str, event: dict):
        """
        :param middleware: `Middleware` instance
        :param name: event name
        :param event: event description
        """
        self.middleware = middleware
        self.name = name
        self.event = event

    async def models(self) -> dict[str, type[BaseModel]] | None:
        """
        Return the models dict (e.g. ``{'Subscription parameters': ..., 'ADDED': ...}``)
        used to generate this event's schema. Subclasses may override to perform
        version-specific lookups.
        """
        return self.event.get("models")


class LegacyEvent(Event):
    """
    Per-version Event whose models are resolved by name against an older API version's
    module. Mirrors :class:`LegacyAPIMethod` for events.
    """

    def __init__(self, middleware: "Middleware", name: str, event: dict, api_version: str,
                 adapter: APIVersionsAdapter):
        super().__init__(middleware, name, event)
        self.api_version = api_version
        self.adapter = adapter

    async def models(self):
        current_models = self.event.get("models") or {}
        result: dict[str, type[BaseModel]] = {}
        for key, current_model in current_models.items():
            unwrap_from = getattr(current_model, "__legacy_unwrap_result_from__", None)
            lookup_name = unwrap_from or current_model.__name__
            try:
                model = await self.adapter.versions[self.api_version].get_model(lookup_name)
            except APIVersionDoesNotContainModelException:
                continue
            if unwrap_from is not None:
                model = _unwrap_event_source_result(model)
            result[key] = model
        return result or None


def _unwrap_event_source_result(event_model: type[BaseModel]) -> type[BaseModel]:
    """
    Recreate the synthesized ``ADDED`` model that lifts the ``result`` field annotation
    of an ``@single_argument_result``-decorated event-source event model.

    The returned model is tagged with ``__legacy_unwrap_result_from__`` so that
    :class:`LegacyEvent` can re-apply the same unwrap when looking up the per-version
    model by name.
    """
    model = create_model(
        event_model.__name__,
        __base__=(BaseModel,),
        __module__=event_model.__module__,
        fields=Annotated[event_model.model_fields["result"].annotation, Field()],
    )
    setattr(model, "__legacy_unwrap_result_from__", event_model.__name__)
    return model

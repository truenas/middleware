import functools
from typing import TYPE_CHECKING, Any

from middlewared.api.base.model import EVENT_MODEL_SUFFIXES, BaseModel, event_model

if TYPE_CHECKING:
    from middlewared.event import EventSource
    from middlewared.main import Middleware


@functools.cache
def event_source_models(event_source: type["EventSource"]) -> dict[str, type[BaseModel] | None]:
    """
    Models that document an event source: its subscription parameters and each event type it sends.

    `event_source.event` declares the payload as its `result` field, which is sent as the event's `fields`, and,
    if the source sends one, the `id` field.

    The first declared event type keeps the bare `event_source.event` name, so the type names generated from earlier
    dumps do not change. The others are named the way CRUD service events are (`...ChangedEvent`, `...RemovedEvent`).

    The result is cached: it does not depend on the API version. Do not mutate it.
    """
    assert event_source.event is not None
    model_fields = event_source.event.model_fields
    result = model_fields["result"]
    id_ = model_fields.get("id")
    base_name = event_source.event.__name__.removesuffix("Event")

    models: dict[str, type[BaseModel] | None] = {"Subscription parameters": event_source.args}
    for i, event_type in enumerate(event_source.event_types):
        models[event_type] = event_model(
            event_source.event.__name__ if i == 0 else base_name + EVENT_MODEL_SUFFIXES[event_type],
            event_source.__module__,
            event_type,
            id_=(id_.annotation, id_) if id_ is not None else None,
            fields=(result.annotation, result),
        )

    return models


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

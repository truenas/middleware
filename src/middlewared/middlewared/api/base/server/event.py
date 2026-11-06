from typing import TYPE_CHECKING, Annotated, Any

from pydantic import Field, create_model

from middlewared.api.base.model import BaseModel

if TYPE_CHECKING:
    from middlewared.event import EventSource
    from middlewared.main import Middleware


def event_source_models(event_source: type["EventSource"]) -> dict[str, type[BaseModel] | None]:
    """
    Models that document an event source: its subscription parameters and each event type it sends.

    `event_source.event` declares the payload as its `result` field; it is sent as the event's `fields`.
    """
    assert event_source.event is not None
    payload = event_source.event.model_fields["result"].annotation
    models: dict[str, type[BaseModel] | None] = {"Subscription parameters": event_source.args}
    for event_type in event_source.event_types:
        attrs: dict[str, Any] = {}
        if event_source.event_id is not None:
            attrs["id"] = Annotated[event_source.event_id, Field()]
        if event_type != "REMOVED":
            attrs["fields"] = Annotated[payload, Field()]

        models[event_type] = create_model(
            # `ADDED` keeps the bare model name so that the type names generated from earlier dumps do not change.
            event_source.event.__name__ + ("" if event_type == "ADDED" else event_type.capitalize()),
            __base__=(BaseModel,),
            __module__=event_source.__module__,
            **attrs,
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

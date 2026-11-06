from pydantic import Field

from middlewared.api.base import BaseModel
from middlewared.api.base.server.event import event_source_models


class Args(BaseModel):
    pass


class Entry(BaseModel):
    name: str = Field(description="Name.")


class EntryEvent(BaseModel):
    result: Entry = Field(description="Entry.")


class DefaultEventSource:
    """Stands in for an `EventSource` subclass that keeps the default event types and sends no `id`."""

    args = Args
    event = EntryEvent
    event_types = ("ADDED",)
    event_id = None


class CollectionEventSource:
    args = Args
    event = EntryEvent
    event_types = ("ADDED", "CHANGED", "REMOVED")
    event_id = str


def test_default_event_source_documents_added_fields_only():
    models = event_source_models(DefaultEventSource)

    assert list(models) == ["Subscription parameters", "ADDED"]
    assert models["Subscription parameters"] is Args
    assert models["ADDED"].__name__ == "EntryEvent"
    assert list(models["ADDED"].model_fields) == ["fields"]
    assert models["ADDED"].model_fields["fields"].annotation is Entry


def test_collection_event_source_documents_each_event_type_with_id():
    models = event_source_models(CollectionEventSource)

    assert list(models) == ["Subscription parameters", "ADDED", "CHANGED", "REMOVED"]
    assert [models[t].__name__ for t in ("ADDED", "CHANGED", "REMOVED")] == [
        "EntryEvent",
        "EntryEventChanged",
        "EntryEventRemoved",
    ]
    assert list(models["ADDED"].model_fields) == ["id", "fields"]
    assert list(models["CHANGED"].model_fields) == ["id", "fields"]
    assert list(models["REMOVED"].model_fields) == ["id"]
    assert models["CHANGED"].model_fields["id"].annotation is str
    assert models["CHANGED"].model_fields["fields"].annotation is Entry

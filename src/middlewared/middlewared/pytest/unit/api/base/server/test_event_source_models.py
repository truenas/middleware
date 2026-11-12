from unittest.mock import Mock

from pydantic import Field
import pytest

from middlewared.api.base import BaseModel
from middlewared.api.base.server.event import event_source_models
from middlewared.event import EventSource


class Args(BaseModel):
    pass


class Entry(BaseModel):
    name: str = Field(description="Name.")


class EntryEvent(BaseModel):
    result: Entry = Field(description="Entry.")


class EntryWithIdEvent(BaseModel):
    id: str = Field(description="Entry ID.")
    result: Entry = Field(description="Entry.")


class DefaultEventSource(EventSource):
    args = Args
    event = EntryEvent


class CollectionEventSource(EventSource):
    args = Args
    event = EntryWithIdEvent
    event_types = ("ADDED", "CHANGED", "REMOVED")


class ChangedOnlyEventSource(EventSource):
    args = Args
    event = EntryEvent
    event_types = ("CHANGED",)


def test_default_event_source_documents_added_fields_only():
    models = event_source_models(DefaultEventSource)

    assert list(models) == ["Subscription parameters", "ADDED"]
    assert models["Subscription parameters"] is Args
    assert models["ADDED"].__name__ == "EntryEvent"
    assert list(models["ADDED"].model_fields) == ["fields"]
    assert models["ADDED"].model_fields["fields"].annotation is Entry
    assert models["ADDED"].model_fields["fields"].description == "Entry."


def test_collection_event_source_documents_each_event_type_with_id():
    models = event_source_models(CollectionEventSource)

    assert list(models) == ["Subscription parameters", "ADDED", "CHANGED", "REMOVED"]
    assert [models[t].__name__ for t in ("ADDED", "CHANGED", "REMOVED")] == [
        "EntryWithIdEvent",
        "EntryWithIdChangedEvent",
        "EntryWithIdRemovedEvent",
    ]
    assert list(models["ADDED"].model_fields) == ["id", "fields"]
    assert list(models["CHANGED"].model_fields) == ["id", "fields"]
    assert list(models["REMOVED"].model_fields) == ["id"]
    assert models["CHANGED"].model_fields["id"].annotation is str
    assert models["CHANGED"].model_fields["id"].description == "Entry ID."
    assert models["CHANGED"].model_fields["fields"].annotation is Entry


def test_first_declared_event_type_keeps_bare_name():
    models = event_source_models(ChangedOnlyEventSource)

    assert list(models) == ["Subscription parameters", "CHANGED"]
    assert models["CHANGED"].__name__ == "EntryEvent"


def test_models_are_built_once():
    assert event_source_models(CollectionEventSource) is event_source_models(CollectionEventSource)


def make_source(event_source: type[EventSource]) -> tuple[EventSource, Mock]:
    send_event = Mock()
    return event_source(Mock(), "test.source", None, send_event, Mock()), send_event


@pytest.mark.parametrize(
    "event_source, event_type, kwargs",
    [
        (DefaultEventSource, "ADDED", {"fields": {}}),
        (CollectionEventSource, "ADDED", {"id": "a", "fields": {}}),
        (CollectionEventSource, "REMOVED", {"id": "a"}),
    ],
)
def test_send_event_passes_documented_frames(event_source, event_type, kwargs):
    source, send_event = make_source(event_source)

    source.send_event(event_type, **kwargs)

    send_event.assert_called_once_with(event_type, **kwargs)


@pytest.mark.parametrize(
    "event_source, event_type, kwargs",
    [
        (DefaultEventSource, "CHANGED", {"fields": {}}),
        (DefaultEventSource, "ADDED", {"id": "a", "fields": {}}),
        (CollectionEventSource, "CHANGED", {"fields": {}}),
        (CollectionEventSource, "REMOVED", {"id": "a", "fields": {}}),
    ],
)
def test_send_event_rejects_undocumented_frames(event_source, event_type, kwargs):
    source, send_event = make_source(event_source)

    with pytest.raises(AssertionError):
        source.send_event(event_type, **kwargs)

    send_event.assert_not_called()

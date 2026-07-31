from typing import Annotated

from pydantic import Field, StringConstraints
from pydantic.json_schema import SkipJsonSchema
import pytest

from middlewared.api.base import (
    BaseModel,
    Excluded,
    ForUpdateMetaclass,
    NotRequired,
    Private,
    excluded_field,
    model_subset,
)
from middlewared.api.base.handler.accept import accept_params, validate_model
from middlewared.api.base.private import is_private_guard
from middlewared.api.v27_0_0.common import QueryArgs
from middlewared.service_exception import ValidationErrors

ERRMSG = "Extra inputs are not permitted"


class Internal(BaseModel):
    name: str
    bypass: Private[bool] = False


class InternalArgs(BaseModel):
    data: Internal


def model_args(model: type[BaseModel]) -> type[BaseModel]:
    """Wrap `model` into an args model that accepts it as a single parameter."""

    class Args(BaseModel):
        data: model  # type: ignore[valid-type]

    return Args


def test_private_field_is_rejected():
    """A `Private` field must be as unspecifiable as a field that does not exist at all."""
    with pytest.raises(ValidationErrors) as ve:
        accept_params(InternalArgs, [{"name": "ivan", "bypass": True}])

    assert ve.value.errors[0].attribute == "data.bypass"
    assert ve.value.errors[0].errmsg == ERRMSG

    with pytest.raises(ValidationErrors) as nonexistent:
        accept_params(InternalArgs, [{"name": "ivan", "nonexistent": True}])

    assert nonexistent.value.errors[0].errmsg == ve.value.errors[0].errmsg


def test_private_field_is_hidden_from_the_schema():
    assert "bypass" not in Internal.model_json_schema()["properties"]
    assert "bypass" not in Internal.schema_model_fields()


def test_private_field_default_is_applied():
    assert accept_params(InternalArgs, [{"name": "ivan"}]) == [{"name": "ivan", "bypass": False}]


def test_private_field_is_allowed_on_opt_in():
    assert accept_params(InternalArgs, [{"name": "ivan", "bypass": True}], allow_private=True) == [
        {"name": "ivan", "bypass": True}
    ]


def test_validate_model_allows_by_default():
    """`validate_model` validates data produced by middleware itself; `accept_params` is the API boundary."""
    assert validate_model(Internal, {"name": "ivan", "bypass": True}) == {"name": "ivan", "bypass": True}

    with pytest.raises(ValidationErrors):
        validate_model(Internal, {"name": "ivan", "bypass": True}, allow_private=False)


def test_model_instance_is_not_revalidated():
    """Internal callers that build the model themselves keep working: pydantic does not revalidate instances."""
    assert accept_params(InternalArgs, [Internal(name="ivan", bypass=True)]) == [{"name": "ivan", "bypass": True}]


def test_validated_params_can_be_forwarded():
    """Middleware methods routinely forward their own validated params to another method.

    `accept_params` materializes every default, private fields included, so a forwarded dict always mentions
    them. That is not the caller specifying anything, so it must be accepted.
    """
    forwarded = accept_params(InternalArgs, [{"name": "ivan"}])
    assert forwarded == [{"name": "ivan", "bypass": False}]
    assert accept_params(InternalArgs, forwarded) == forwarded


def test_query_options_can_be_forwarded():
    """Regression: `audit.query` validates its params and forwards `query-options` to `auditbackend.query`."""
    options = accept_params(QueryArgs, [[], {"count": True}])[1]
    assert options["delete_invalid_rows"] is False
    assert accept_params(QueryArgs, [[], options]) == [[], options]


def test_skip_json_schema_field_stays_settable():
    """Plain `SkipJsonSchema` keeps its meaning: undocumented, but not rejected."""

    class Model(BaseModel):
        name: str
        undocumented: SkipJsonSchema[bool] = False

    class Args(BaseModel):
        data: Model

    assert accept_params(Args, [{"name": "ivan", "undocumented": True}]) == [{"name": "ivan", "undocumented": True}]
    assert "undocumented" not in Model.model_json_schema()["properties"]
    assert "undocumented" not in Model.schema_model_fields()
    assert not any(is_private_guard(metadata) for metadata in Model.model_fields["undocumented"].metadata)


def test_excluded_field_is_not_guarded():
    """`Excluded` is `SkipJsonSchema`, not `Private`, and already rejects any supplied value on its own."""

    class Object(BaseModel):
        id: int
        name: str

    class CreateObject(Object):
        id: Excluded = excluded_field()

    assert not any(is_private_guard(metadata) for metadata in CreateObject.model_fields["id"].metadata)

    with pytest.raises(ValidationErrors) as ve:
        accept_params(model_args(CreateObject), [{"id": 1, "name": "ivan"}])

    assert ve.value.errors[0].errmsg == ERRMSG


def test_not_required_private_field():
    """A `NotRequired` default must not hide `Private` from the schema or from the guard.

    `_annotate_not_required` folds field metadata into the annotation, where `SkipJsonSchema` stops being
    honored, so both markers have to be kept at field level.
    """

    class Model(BaseModel):
        name: str
        bypass: Private[bool] = NotRequired

    assert "bypass" not in Model.model_json_schema()["properties"]
    assert "bypass" not in Model.schema_model_fields()

    with pytest.raises(ValidationErrors) as ve:
        accept_params(model_args(Model), [{"name": "ivan", "bypass": True}])

    assert ve.value.errors[0].attribute == "data.bypass"
    assert accept_params(model_args(Model), [{"name": "ivan"}]) == [{"name": "ivan"}]


def test_not_required_constraints_are_still_folded():
    """Keeping the markers at field level must not stop constraints from being folded into the typed arm."""

    class Model(BaseModel):
        value: Private[Annotated[str, StringConstraints(max_length=3)]] = NotRequired

    assert validate_model(Model, {"value": "abc"}) == {"value": "abc"}

    with pytest.raises(ValidationErrors):
        validate_model(Model, {"value": "abcd"})


def test_guard_is_added_once_per_field():
    """Each subclass rebuilds its `FieldInfo` from the already-guarded one of its base."""

    class Child(Internal):
        pass

    class GrandChild(Child):
        pass

    for model in (Internal, Child, GrandChild):
        guards = [m for m in model.model_fields["bypass"].metadata if is_private_guard(m)]
        assert len(guards) == 1, model


def test_subclass_may_override_the_default():
    """The guard compares against the default of the field it is on, not the one its base declared."""

    class Child(Internal):
        bypass: Private[bool] = True

    assert accept_params(model_args(Child), [{"name": "ivan", "bypass": True}]) == [{"name": "ivan", "bypass": True}]

    with pytest.raises(ValidationErrors) as ve:
        accept_params(model_args(Child), [{"name": "ivan", "bypass": False}])

    assert ve.value.errors[0].attribute == "data.bypass"


def test_for_update_metaclass_is_guarded():
    """`ForUpdateMetaclass` does not go through `_BaseModelMetaclass.__new__`."""

    class Update(Internal, metaclass=ForUpdateMetaclass):
        pass

    with pytest.raises(ValidationErrors) as ve:
        accept_params(model_args(Update), [{"bypass": True}])

    assert ve.value.errors[0].attribute == "data.bypass"
    assert accept_params(model_args(Update), [{"name": "ivan"}]) == [{"name": "ivan"}]


def test_model_subset_is_guarded():
    """`model_subset` deletes fields after the class is built; the guard travels with the field it is on."""
    Subset = model_subset(Internal, ["name", "bypass"])

    with pytest.raises(ValidationErrors) as ve:
        accept_params(model_args(Subset), [{"name": "ivan", "bypass": True}])

    assert ve.value.errors[0].attribute == "data.bypass"


def test_nested_private_field():
    class Options(BaseModel):
        delete_invalid_rows: Private[bool] = False

    class Query(BaseModel):
        options: Options = Field(default_factory=Options)

    class QueryArgs(BaseModel):
        data: Query

    with pytest.raises(ValidationErrors) as ve:
        accept_params(QueryArgs, [{"options": {"delete_invalid_rows": True}}])

    assert ve.value.errors[0].attribute == "data.options.delete_invalid_rows"

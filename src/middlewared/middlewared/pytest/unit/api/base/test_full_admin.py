import asyncio
from typing import Annotated, Literal, Union

from pydantic import Discriminator, Field, Secret
import pytest

from middlewared.api.base import BaseModel, ForUpdateMetaclass, FullAdmin, LongString
from middlewared.api.base.handler.full_admin import full_admin_fields, full_admin_payload_fields
from middlewared.service.full_admin import check_full_admin_payload
from middlewared.service_exception import ValidationErrors
from middlewared.utils.privilege import check_full_admin_fields

ERRMSG = "Changes to this parameter are restricted to users with full administrative privileges."


class Nested(BaseModel):
    aux: FullAdmin[str] = Field(default="")
    ordinary: str = Field(default="")


class Task(BaseModel):
    name: str
    extra: FullAdmin[list[str]] = Field(default_factory=list)
    nested: Nested = Field(default_factory=Nested)
    secret: FullAdmin[Secret[LongString]] = Field(default="")


class TaskCreateArgs(BaseModel):
    task_create: Task


class TaskUpdate(Task, metaclass=ForUpdateMetaclass):
    pass


class TaskUpdateArgs(BaseModel):
    id: int
    task_update: TaskUpdate


def check(fields, new, old=None):
    verrors = ValidationErrors()
    check_full_admin_fields("task_create", fields, new, old, verrors)
    return [error.attribute for error in verrors.errors]


class TestFieldCollection:
    def test_payload_is_the_last_parameter(self):
        assert full_admin_payload_fields(TaskCreateArgs)[0] == "task_create"
        assert full_admin_payload_fields(TaskUpdateArgs)[0] == "task_update"

    def test_finds_nested_fields(self):
        assert {field.path for field in full_admin_fields(Task)} == {
            ("extra",),
            ("nested", "aux"),
            ("secret",),
        }

    def test_records_defaults(self):
        assert {field.path: field.default for field in full_admin_fields(Task)} == {
            ("extra",): [],
            ("nested", "aux"): "",
            ("secret",): "",
        }

    def test_finds_fields_behind_a_discriminated_union(self):
        class Left(BaseModel):
            kind: Literal["left"]
            aux: FullAdmin[str] = Field(default="")

        class Right(BaseModel):
            kind: Literal["right"]

        class Share(BaseModel):
            options: Annotated[Union[Left, Right], Discriminator("kind")] | None = None

        assert {field.path for field in full_admin_fields(Share)} == {("options", "aux")}

    def test_rejects_a_marked_field_inside_a_collection(self):
        class Item(BaseModel):
            aux: FullAdmin[str] = Field(default="")

        class Container(BaseModel):
            items: list[Item] = Field(default_factory=list)

        with pytest.raises(TypeError, match="collection whose items declare `FullAdmin`"):
            full_admin_fields(Container)

    def test_no_marked_fields(self):
        class Plain(BaseModel):
            name: str

        class PlainArgs(BaseModel):
            data: Plain

        assert full_admin_fields(Plain) == ()
        assert full_admin_payload_fields(PlainArgs) == ("", ())


class TestCreate:
    """On create there is nothing stored, so the baseline is the field's default."""

    def test_silence_is_allowed(self):
        assert check(full_admin_fields(Task), {"name": "t"}) == []

    def test_the_default_is_allowed(self):
        assert check(full_admin_fields(Task), {"name": "t", "extra": [], "secret": ""}) == []

    def test_a_value_is_rejected(self):
        assert check(full_admin_fields(Task), {"name": "t", "extra": ["-e", "sh"]}) == ["task_create.extra"]

    def test_a_nested_value_is_rejected(self):
        assert check(full_admin_fields(Task), {"nested": {"aux": "x"}}) == ["task_create.nested.aux"]

    def test_an_unmentioned_nested_model_is_allowed(self):
        assert check(full_admin_fields(Task), {"nested": {"ordinary": "x"}}) == []

    def test_every_offending_field_is_reported(self):
        assert check(full_admin_fields(Task), {"extra": ["x"], "nested": {"aux": "y"}, "secret": "z"}) == [
            "task_create.extra",
            "task_create.nested.aux",
            "task_create.secret",
        ]


class TestUpdate:
    """On update the baseline is what is stored, so only an actual change is rejected."""

    OLD = {"name": "t", "extra": ["--stats"], "nested": {"aux": "keep"}, "secret": "s"}

    def test_echoing_the_stored_value_is_allowed(self):
        assert check(full_admin_fields(Task), dict(self.OLD), self.OLD) == []

    def test_editing_an_unrelated_field_is_allowed(self):
        assert check(full_admin_fields(Task), {**self.OLD, "name": "renamed"}, self.OLD) == []

    def test_a_change_is_rejected(self):
        assert check(full_admin_fields(Task), {"extra": ["-e", "sh"]}, self.OLD) == ["task_create.extra"]

    def test_clearing_is_rejected(self):
        assert check(full_admin_fields(Task), {"extra": []}, self.OLD) == ["task_create.extra"]

    def test_a_nested_change_is_rejected(self):
        assert check(full_admin_fields(Task), {"nested": {"aux": "other"}}, self.OLD) == ["task_create.nested.aux"]

    def test_falls_back_to_the_default_when_the_stored_entry_has_no_counterpart(self):
        old = {"name": "t"}
        assert check(full_admin_fields(Task), {"extra": []}, old) == []
        assert check(full_admin_fields(Task), {"extra": ["x"]}, old) == ["task_create.extra"]


class TestPayloadShapes:
    def test_none_is_a_value_like_any_other(self):
        class Optional_(BaseModel):
            aux: FullAdmin[str | None] = Field(default=None)

        fields = full_admin_fields(Optional_)
        assert check(fields, {"aux": None}) == []
        assert check(fields, {"aux": "x"}) == ["task_create.aux"]
        assert check(fields, {"aux": None}, {"aux": "stored"}) == ["task_create.aux"]

    def test_reads_a_validated_model_instance(self):
        """`check_annotations=True` methods receive their payload as a model rather than as a dict."""
        fields = full_admin_fields(Task)
        assert check(fields, Task(name="t")) == []
        assert check(fields, Task(name="t", extra=["-e", "sh"])) == ["task_create.extra"]

    def test_a_null_nested_model_is_not_a_value(self):
        class Share(BaseModel):
            options: Nested | None = None

        assert check(full_admin_fields(Share), {"options": None}) == []


def test_an_aliased_marked_field_is_refused():
    """`populate_by_name` would let a caller supply it under the field name, which the check never looks at."""

    class Aliased(BaseModel):
        options_: FullAdmin[str] = Field(default="", alias="options")

    with pytest.raises(TypeError, match="`FullAdmin` field with an alias"):
        full_admin_fields(Aliased)


class _Credential:
    is_user_session = True
    allowlist = None
    user = {"privilege": {"roles": ["SOME_WRITE"]}}


class _FullAdminCredential(_Credential):
    user = {"privilege": {"roles": ["FULL_ADMIN"]}}


def _app(credential):
    return type("App", (), {"authenticated_credentials": credential})()


def _method(model):
    return type("Method", (), {"new_style_accepts": model})()


def _payload(data, old=None, credential=None):
    """Drive `check_full_admin_payload` the way `CRUDService` and `ConfigService` do."""
    return asyncio.run(
        check_full_admin_payload(
            _app(credential) if credential is not None else None,
            _method(TaskCreateArgs),
            data,
            (lambda: asyncio.sleep(0, old)) if old is not None else None,
        )
    )


class TestCheckFullAdminPayload:
    """The wrapper the CRUD and config services call, including how it normalises the stored entry."""

    def test_reads_a_stored_entry_model(self):
        """A `generic` service returns the entry model rather than a dict, and dumping it must not raise.

        Regression test: passing `expose_secrets` in `context` raises `ValueError` out of
        `DumpableModel.model_dump`, which broke every non-FULL_ADMIN update.
        """
        stored = Task(name="t", extra=["--stats"])

        _payload({"name": "renamed"}, stored, _Credential())
        _payload({"extra": ["--stats"]}, stored, _Credential())

        with pytest.raises(ValidationErrors) as ve:
            _payload({"extra": ["-e", "sh"]}, stored, _Credential())

        assert [error.attribute for error in ve.value.errors] == ["task_create.extra"]

    def test_reads_a_stored_dict(self):
        """A non-`generic` service returns a plain dict."""
        stored = {"name": "t", "extra": ["--stats"]}

        _payload({"extra": ["--stats"]}, stored, _Credential())

        with pytest.raises(ValidationErrors):
            _payload({"extra": ["-e", "sh"]}, stored, _Credential())

    def test_a_full_admin_is_not_checked(self):
        _payload({"extra": ["-e", "sh"]}, None, _FullAdminCredential())

    def test_an_internal_call_is_not_checked(self):
        _payload({"extra": ["-e", "sh"]})

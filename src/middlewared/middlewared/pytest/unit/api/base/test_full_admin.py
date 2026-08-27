import asyncio
from typing import Annotated, Literal, Union

from pydantic import Discriminator, Field, Secret
import pytest

from middlewared.api.base import BaseModel, ForUpdateMetaclass, FullAdmin, LongString
from middlewared.api.base.full_admin import RESTRICTION
from middlewared.api.base.handler.full_admin import full_admin_fields, full_admin_payload_fields
from middlewared.service.full_admin import check_full_admin_payload
from middlewared.service_exception import ValidationErrors
from middlewared.utils.privilege import check_full_admin_fields


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
    # Every rejection carries the one shared wording, which names the role the caller is missing.
    assert all(error.errmsg == RESTRICTION for error in verrors.errors), verrors.errors
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

    with pytest.raises(TypeError, match="reached through aliased field"):
        full_admin_fields(Aliased)


def test_an_aliased_field_on_the_path_is_refused():
    """An aliased *ancestor* defeats the check just as thoroughly as an aliased marked field."""

    class Nested_(BaseModel):
        aux: FullAdmin[str] = Field(default="")

    class Outer(BaseModel):
        options_: Nested_ = Field(default=None, alias="options")

    with pytest.raises(TypeError, match="reached through aliased field"):
        full_admin_fields(Outer)


def test_finds_a_field_wrapped_in_secret():
    """`Secret[SomeModel]` is a shape the API really uses, e.g. keychain credential attributes."""

    class Inner(BaseModel):
        aux: FullAdmin[str] = Field(default="")

    class Outer(BaseModel):
        blob: Secret[Inner] = Field(default=None)

    assert {field.path for field in full_admin_fields(Outer)} == {("blob", "aux")}


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


def test_an_unset_for_update_field_is_not_a_supplied_value():
    """A `check_annotations` method receives a model instance; its unset fields hold the `undefined` sentinel.

    Reading that as a supplied value would reject every marked field the caller never mentioned.
    """
    stored = {"name": "t", "extra": ["--stats"], "nested": {"aux": "keep"}, "secret": "s"}

    assert check(full_admin_fields(TaskUpdate), TaskUpdate(name="renamed"), stored) == []


def test_the_stored_entry_is_not_loaded_when_nothing_marked_is_supplied():
    """`get_old` is a full entry query for most services, so it must not run on an unrelated edit."""
    loaded = False

    async def get_old():
        nonlocal loaded
        loaded = True
        return Task(name="t")

    asyncio.run(
        check_full_admin_payload(
            _app(_Credential()),
            _method(TaskCreateArgs),
            {"name": "renamed"},
            get_old,
        )
    )
    assert not loaded

    asyncio.run(
        check_full_admin_payload(
            _app(_Credential()),
            _method(TaskCreateArgs),
            {"extra": []},
            get_old,
        )
    )
    assert loaded


def test_an_app_without_credentials_is_checked():
    """Fail closed: an `app` carrying no credentials is not a full admin, so it must not be waved through."""
    with pytest.raises(ValidationErrors):
        asyncio.run(
            check_full_admin_payload(
                _app(None),
                _method(TaskCreateArgs),
                {"extra": ["-e", "sh"]},
                None,
            )
        )


def test_the_error_names_the_role_and_matches_the_documented_wording():
    """The description note and the validation error are the same sentence, so they cannot drift apart."""
    verrors = ValidationErrors()
    check_full_admin_fields("task_create", full_admin_fields(Task), {"extra": ["-e", "sh"]}, None, verrors)

    assert [error.errmsg for error in verrors.errors] == [RESTRICTION]
    assert "FULL_ADMIN" in RESTRICTION
    assert Task.model_fields["extra"].description.endswith(RESTRICTION)

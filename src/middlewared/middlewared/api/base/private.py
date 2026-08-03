from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel as PydanticBaseModel
from pydantic import WrapValidator
from pydantic.fields import FieldInfo
from pydantic.json_schema import SkipJsonSchema
from pydantic_core import PydanticCustomError, core_schema

__all__ = ["Private", "private_fields"]


if TYPE_CHECKING:
    # Like pydantic does for `SkipJsonSchema` itself, declare an alias for type checkers so that `Private[bool]`
    # is understood as an annotation rather than as a subscripted class.
    type Private[T] = Annotated[T, ...]
else:

    class Private(SkipJsonSchema):
        """Marks a field that is internal to middleware.

        Like `SkipJsonSchema`, the field is kept out of the published API schema. On top of that, `accept_params`
        rejects any attempt to specify it exactly the way it rejects an unknown key.
        """


class _RejectPrivate:
    """Rejects a value supplied for a `Private` field, unless that value is the field's default.

    A middleware method routinely forwards its own validated params to another method, and `accept_params`
    materializes every default in what it returns, private fields included. A forwarded dict therefore always
    mentions them, which is not the caller specifying anything. Only a value that actually differs from the
    default is rejected.
    """

    def __init__(self, default: Any):
        self.default = default

    def __call__(
        self,
        value: Any,
        handler: core_schema.ValidatorFunctionWrapHandler,
        info: core_schema.ValidationInfo,
    ) -> Any:
        # Pydantic does not validate defaults, so this only runs when a value was actually supplied.
        if isinstance(info.context, dict) and info.context.get("allow_private") is False and value != self.default:
            # Deliberately the same error an unknown key produces: a private field must be indistinguishable
            # from a nonexistent one.
            raise PydanticCustomError("", "Extra inputs are not permitted")

        return handler(value)


def is_private_guard(metadata: Any) -> bool:
    """Whether `metadata` is the validator that `guard_private_fields` attaches."""
    return isinstance(metadata, WrapValidator) and isinstance(metadata.func, _RejectPrivate)


def _is_private(field: FieldInfo) -> bool:
    """Whether `field` is `Private`, i.e. must not be settable by API callers."""
    return any(isinstance(metadata, Private) for metadata in field.metadata)  # type: ignore[arg-type, misc]


def private_fields(cls: type[PydanticBaseModel]) -> list[str]:
    """Names of the `Private` fields declared directly on `cls` (not on its nested models)."""
    return [name for name, field in cls.model_fields.items() if _is_private(field)]


def _guard(field: FieldInfo) -> _RejectPrivate | None:
    """The validator already attached to `field`, if any."""
    for metadata in field.metadata:
        if isinstance(metadata, WrapValidator) and isinstance(metadata.func, _RejectPrivate):
            return metadata.func

    return None


def guard_private_fields(cls: type[PydanticBaseModel]) -> bool:
    """Attach a rejecting validator to every `Private` field of `cls`.

    :return: whether any field was modified (in which case the caller must rebuild the model).
    """
    modified = False
    for field in cls.model_fields.values():
        if not _is_private(field):
            continue

        guard = _guard(field)
        if guard is not None and guard.default == field.default:
            # A subclass builds its own `FieldInfo` from the (already guarded) one of its base, so the guard
            # must not be added a second time. It is replaced rather than kept when the subclass declares a
            # different default, since the guard has to compare against the default of the field it is on.
            continue

        field.metadata = [
            *(metadata for metadata in field.metadata if not is_private_guard(metadata)),
            WrapValidator(_RejectPrivate(field.default)),
        ]
        modified = True

    return modified

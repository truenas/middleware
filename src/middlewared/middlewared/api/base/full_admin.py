from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel as PydanticBaseModel
from pydantic.fields import FieldInfo

__all__ = ["FullAdmin", "FullAdminOnly", "document_full_admin_fields", "is_full_admin_field"]


RESTRICTION = "Only a user with the `FULL_ADMIN` role may set or change this field."


@dataclass(frozen=True)
class FullAdminOnly:
    """Field metadata attached by `FullAdmin`.

    Frozen so that pydantic can hash it along with the rest of a field's metadata.
    """


if TYPE_CHECKING:
    # Like pydantic does for `SkipJsonSchema`, declare an alias for type checkers so that `FullAdmin[str]` is
    # understood as an annotation rather than as a subscripted class.
    type FullAdmin[T] = Annotated[T, ...]
else:

    class FullAdmin:
        """Marks a field that only a `FULL_ADMIN` credential may set or change.

        Use it for a field whose value middleware passes through unvalidated to a root command line or to the
        configuration file of a privileged daemon. Such a field hands its caller a capability that the role
        guarding the endpoint was never meant to grant, so mutating it requires the one role that grants
        everything anyway.

        Unlike `Private`, the field stays in the published API schema: it remains a documented part of the
        endpoint, and a full administrator may still use it. Note also that no validator is attached here.
        Deciding whether a value *changes* anything needs the currently stored entry, which pydantic does not
        have, so enforcement lives in the service layer (see `middlewared.utils.privilege`).
        """

        def __class_getitem__(cls, item: Any) -> Any:
            return Annotated[item, FullAdminOnly()]


def is_full_admin_field(field: FieldInfo) -> bool:
    """Whether `field` is marked `FullAdmin`."""
    return any(isinstance(metadata, FullAdminOnly) for metadata in field.metadata)


def document_full_admin_fields(cls: type[PydanticBaseModel]) -> bool:
    """Note the restriction in the description of every `FullAdmin` field of `cls`.

    The field stays in the published API schema, so its description is where a caller finds out why they got a
    validation error. Doing it here rather than by hand keeps the wording uniform and impossible to forget.

    :return: whether any description was changed (in which case the caller must rebuild the model, or the
        already-built schema keeps the undocumented description).
    """
    modified = False
    for field in cls.model_fields.values():
        if not is_full_admin_field(field):
            continue

        description = field.description or ""
        if RESTRICTION in description:
            # A subclass builds its own `FieldInfo` from the (already documented) one of its base.
            continue

        field.description = f"{description}\n\n{RESTRICTION}".strip()
        modified = True

    return modified

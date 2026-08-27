import functools
import typing
from typing import Annotated, Any

from pydantic import Secret
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from middlewared.api.base import BaseModel
from middlewared.api.base.full_admin import is_full_admin_field
from middlewared.utils.typing_ import is_union

__all__ = ["FullAdminField", "full_admin_fields", "full_admin_payload_fields"]


class FullAdminField(typing.NamedTuple):
    """A `FullAdmin` field found inside a method's payload.

    :ivar path: the field's location within the payload, as the sequence of keys leading to it.
    :ivar default: the comparison baseline when the payload being checked has no stored counterpart (i.e. on
        create). This is the field's default, except on a `ForUpdateMetaclass` model, where every default is the
        `undefined` sentinel; nothing compares equal to it, so such a field fails closed.
    """

    path: tuple[str, ...]
    default: Any


@functools.cache
def full_admin_fields(model: type[BaseModel]) -> tuple[FullAdminField, ...]:
    """Every `FullAdmin` field of `model`, including those of the models it nests.

    :param model: any API model.
    :return: the fields, each with the sequence of keys leading to it from `model`.
    """
    return tuple(_walk(model, (), frozenset()))


@functools.cache
def full_admin_payload_fields(accepts: type[BaseModel]) -> tuple[str, tuple[FullAdminField, ...]]:
    """The `FullAdmin` fields of the payload that `accepts` wraps.

    Every CRUD and config method takes its payload as its last parameter, so that is the model to walk. The name
    of that parameter is returned alongside the fields: it is the prefix `accept_params` puts on validation errors
    for the same payload (`smb_update`, `rsync_task_create`, `data`, ...), so errors raised against these fields
    read the same way as any other validation error on the endpoint.

    Methods whose payload is not the last parameter have to name their model themselves; see `full_admin_fields`.

    :param accepts: the `new_style_accepts` model of a method.
    :return: the payload parameter's name, and its `FullAdmin` fields. Both are empty if there are none.
    """
    if not accepts.model_fields:
        return "", ()

    name, field = list(accepts.model_fields.items())[-1]
    if not (fields := tuple(_walk(field.annotation, (), frozenset()))):
        return "", ()

    return field.alias or name, fields


def _walk(
    annotation: Any,
    prefix: tuple[str, ...],
    seen: frozenset[type[BaseModel]],
    aliased: tuple[str, ...] = (),
) -> typing.Iterator[FullAdminField]:
    """Yield every `FullAdmin` field reachable from `annotation`, prefixed with `prefix`.

    :param aliased: fields already crossed on this path whose alias differs from their name. Enforcement
        addresses a field by one key per level, but `populate_by_name` accepts either, so any such field -- the
        marked one or an ancestor of it -- would let a caller sidestep the check.
    """
    for model in _models(annotation):
        if model in seen:
            # Models may reference each other; re-entering one would not terminate. A marked field hanging off a
            # re-entered model is therefore missed. No model in the API has that shape, and the coverage test
            # would not catch it, so do not give a marked field a cyclic home.
            continue

        for name, field in model.model_fields.items():
            path = prefix + (field.alias or name,)
            is_aliased = field.alias is not None and field.alias != name
            if is_full_admin_field(field):
                if offenders := (*aliased, f"{model.__name__}.{name}") if is_aliased else aliased:
                    raise TypeError(
                        f"{'.'.join(path)} is a `FullAdmin` field reached through aliased field(s) "
                        f"{', '.join(offenders)}. This is not supported: `populate_by_name` lets a caller supply "
                        f"an aliased field under either key, but enforcement addresses it by one. Please drop the "
                        f"alias or rename the field."
                    )

                yield FullAdminField(path, _default(field))
                continue

            yield from _walk(
                field.annotation,
                path,
                seen | {model},
                (*aliased, f"{model.__name__}.{name}") if is_aliased else aliased,
            )

            for element in _elements(field.annotation):
                if next(_walk(element, path, seen | {model}, aliased), None) is not None:
                    raise TypeError(
                        f"{model.__name__}.{name} is a collection whose items declare `FullAdmin` field(s). This "
                        f"is not supported: such a field is addressed by the sequence of keys leading to it, which "
                        f"cannot name a collection item. Please, mark the collection itself instead."
                    )


def _models(annotation: Any) -> typing.Iterator[type[BaseModel]]:
    """Every API model that `annotation` may resolve to at the same nesting level."""
    for candidate in _unwrap(annotation):
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            yield candidate


def _elements(annotation: Any) -> typing.Iterator[Any]:
    """Annotations of the items of `annotation`, if it is a collection of something."""
    for candidate in _unwrap(annotation):
        origin = typing.get_origin(candidate)
        if origin in (list, set, frozenset, tuple):
            yield from typing.get_args(candidate)
        elif origin is dict and len(args := typing.get_args(candidate)) == 2:
            yield args[1]


def _unwrap(annotation: Any) -> typing.Iterator[Any]:
    """Strip `Annotated` and `Secret`, and flatten unions, leaving the types `annotation` may actually hold."""
    origin = typing.get_origin(annotation)
    if origin is Annotated:
        yield from _unwrap(typing.get_args(annotation)[0])
    elif origin is Secret:
        # `Secret` is a transparent wrapper, and `Secret[SomeModel]` is a shape the API really uses.
        yield from _unwrap(typing.get_args(annotation)[0])
    elif is_union(origin):
        for arg in typing.get_args(annotation):
            yield from _unwrap(arg)
    else:
        yield annotation


def _default(field: FieldInfo) -> Any:
    try:
        default = field.get_default(call_default_factory=True)
    except (TypeError, ValueError):
        # A `default_factory` that consumes already-validated data cannot be resolved outside of validation. No
        # supplied value compares equal to this, so such a field is treated as always changed.
        return PydanticUndefined

    if isinstance(default, Secret):
        # `validate_default` wraps the default of a `Secret` field. Unwrap it so that it compares equal to the
        # plain value the caller supplies.
        return default.get_secret_value()

    return default

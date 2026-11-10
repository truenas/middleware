from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

__all__ = ["Multiline", "MultilineAllowed", "add_line_break_validators", "validate_no_line_breaks"]


_HANDLED = "truenas_line_breaks_handled"


def validate_no_line_breaks(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise ValueError("Line breaks are not allowed")

    return value


@dataclass(frozen=True)
class MultilineAllowed:
    """Annotation metadata attached by `Multiline`.

    Frozen so that pydantic can hash it along with the rest of a field's metadata.
    """

    def __get_pydantic_core_schema__(self, source: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        schema = dict(handler(source))
        metadata = schema.get("metadata")
        if metadata is None:
            metadata = {}

        schema["metadata"] = {**metadata, _HANDLED: True}
        return schema


if TYPE_CHECKING:
    # Like pydantic does for `SkipJsonSchema`, declare an alias for type checkers so that `Multiline[str]`
    # is understood as an annotation rather than as a subscripted class.
    type Multiline[T] = Annotated[T, ...]
else:

    class Multiline:
        """Marks a string that may carry a line break."""

        def __class_getitem__(cls, item: Any) -> Any:
            return Annotated[item, MultilineAllowed()]


def add_line_break_validators(schema: core_schema.CoreSchema) -> core_schema.CoreSchema:
    """Attach `validate_no_line_breaks` to every `str` node of `schema` that `Multiline` did not opt out.

    The result is idempotent: a node this function wrapped is left alone on a second pass.
    """
    walked: core_schema.CoreSchema = _walk(schema)
    return walked


def _walk(node: Any) -> Any:
    if isinstance(node, dict):
        if not isinstance(node.get("type"), str):
            # A dict that is not a schema node maps names to schemas, as `fields` and `choices` do. Its
            # keys are a caller's names, so none of them may be read as a key of a schema.
            return {key: _walk(value) for key, value in node.items()}

        if (node.get("metadata") or {}).get(_HANDLED):
            return node

        if node["type"] == "str":
            wrapped = core_schema.no_info_after_validator_function(validate_no_line_breaks, node)
            wrapped["metadata"] = {_HANDLED: True}
            return wrapped

        return {
            # `default` and `metadata` hold a caller's values, and `serialization` only ever runs on the
            # way out, so a value under any of them must not be rewritten into a validator.
            key: value if key in ("default", "metadata", "serialization") else _walk(value)
            for key, value in node.items()
        }

    if isinstance(node, list):
        return [_walk(item) for item in node]

    return node

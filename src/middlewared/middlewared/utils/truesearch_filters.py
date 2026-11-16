"""
This module is the translation layer of `truesearch.query`.

A user writes filters with simple field names, for example `name` or `size`. truesearchd reads a macOS Spotlight
query. This module converts the filters into that query.

Two tables control the translation:

* `FIELDS` gives the Spotlight attribute of each field, and the type of its values.
* `TEXT_OPERATORS` and the other operator tables give the Spotlight form of each operator.

To add a field, add a row to `FIELDS`. Then document the field in the `query-filters` description of the current API
version. A unit test checks that the description names each field and each choice.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import enum
from types import MappingProxyType
from typing import Any

from middlewared.api.base.validators.filters import TIMESTAMP_DESIGNATOR

# A Spotlight query uses these characters as wildcards and quotes. A value must escape them.
_SPECIAL = MappingProxyType(str.maketrans({char: "\\" + char for char in '\\"*?'}))


class FieldType(enum.Enum):
    TEXT = "Text"
    TAGS = "Tag"
    NUMBER = "Number"
    DATE = "Date"
    CHOICE = "Choice"


# The Spotlight comparison of each text operator, and the pattern around the value. `*` matches any text.
TEXT_OPERATORS = MappingProxyType(
    {
        "=": ("==", "{}"),
        "!=": ("!=", "{}"),
        "^": ("==", "{}*"),
        "!^": ("!=", "{}*"),
        "$": ("==", "*{}"),
        "!$": ("!=", "*{}"),
        "rin": ("==", "*{}*"),
        "rnin": ("!=", "*{}*"),
    }
)
# A tag must agree with the full value.
TAG_OPERATORS = MappingProxyType(
    {
        "rin": ("==", "{}"),
        "rnin": ("!=", "{}"),
    }
)
# The Spotlight comparison of each number, date or choice operator.
COMPARISONS = MappingProxyType({"=": "==", "!=": "!=", ">": ">", ">=": ">=", "<": "<", "<=": "<="})
# The operators of each type. `in` and `nin` compare with each value of a list.
OPERATORS = MappingProxyType(
    {
        FieldType.TEXT: tuple(TEXT_OPERATORS) + ("in", "nin"),
        FieldType.TAGS: tuple(TAG_OPERATORS),
        FieldType.NUMBER: tuple(COMPARISONS) + ("in", "nin"),
        FieldType.DATE: tuple(COMPARISONS),
        FieldType.CHOICE: ("=", "!=", "in", "nin"),
    }
)
# These types also take each operator with `C` before it. `C` ignores case and accents.
_CASELESS = frozenset({FieldType.TEXT, FieldType.TAGS})


@dataclass(frozen=True, slots=True)
class QueryField:
    """One field of `truesearch.query`: its Spotlight attribute, the type of its values, and its choices."""

    attribute: str
    type: FieldType
    # The Spotlight value of each choice of a choice field.
    choices: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))


FIELDS: Mapping[str, QueryField] = MappingProxyType(
    {
        "name": QueryField("kMDItemFSName", FieldType.TEXT),
        "type": QueryField(
            "kMDItemContentTypeTree",
            FieldType.CHOICE,
            MappingProxyType({"DIRECTORY": "public.directory", "FILE": "public.data", "SYMLINK": "public.symlink"}),
        ),
        "size": QueryField("kMDItemFSSize", FieldType.NUMBER),
        "uid": QueryField("kMDItemFSOwnerUserID", FieldType.NUMBER),
        "gid": QueryField("kMDItemFSOwnerGroupID", FieldType.NUMBER),
        "mtime": QueryField("kMDItemFSContentChangeDate", FieldType.DATE),
        "btime": QueryField("kMDItemFSCreationDate", FieldType.DATE),
        "atime": QueryField("kMDItemLastUsedDate", FieldType.DATE),
        "macos_kind": QueryField(
            "kMDItemKind",
            FieldType.CHOICE,
            MappingProxyType(
                {
                    "FOLDER": "Folder",
                    "PDF": "PDF",
                    "IMAGE": "Image",
                    "MOVIE": "Movie",
                    "AUDIO": "Audio",
                    "TEXT": "Text",
                    "DOCUMENT": "Document",
                    "SPREADSHEET": "Spreadsheet",
                    "PRESENTATION": "Presentation",
                    "ARCHIVE": "Archive",
                    "APPLICATION": "Application",
                    "DISK_IMAGE": "Disk Image",
                    "PACKAGE": "Package",
                    "FONT": "Font",
                    "CONTACT": "Contact",
                    "MAIL": "Mail",
                }
            ),
        ),
        "tags": QueryField("kMDItemUserTags", FieldType.TAGS),
        "comment": QueryField("kMDItemFinderComment", FieldType.TEXT),
    }
)


def spotlight_query(filters: list[Any]) -> str:
    """
    Convert query-filters into one Spotlight query. If there are no filters, the query matches all entries. If a
    filter is not valid, raise a `ValueError` that tells the user why.
    """
    if not filters:
        return f'{FIELDS["name"].attribute} == "*"'

    return _all(filters)


def _join(parts: list[str], operator: str) -> str:
    return parts[0] if len(parts) == 1 else "(" + f" {operator} ".join(parts) + ")"


def _all(filters: Any) -> str:
    """All filters of a list must match."""
    if not isinstance(filters, (list, tuple)) or not filters:
        raise ValueError(f"{filters!r} is not a list of filters.")

    return _join([_term(item) for item in filters], "&&")


def _term(item: Any) -> str:
    """One filter, or an `OR` of filters. Each branch of an `OR` is a filter, a list of filters, or an `OR`."""
    if isinstance(item, (list, tuple)) and len(item) == 2 and item[0] == "OR":
        branches = item[1]
        if not isinstance(branches, (list, tuple)) or not branches:
            raise ValueError('"OR" must have a list of filters.')

        return _join(
            [
                _all(branch)
                if isinstance(branch, (list, tuple)) and branch and isinstance(branch[0], (list, tuple))
                else _term(branch)
                for branch in branches
            ],
            "||",
        )

    if not isinstance(item, (list, tuple)) or len(item) != 3 or not all(isinstance(part, str) for part in item[:2]):
        raise ValueError(f"{item!r} is not a filter. A filter is a list of a field, an operator, and a value.")

    return _comparison(*item)


def _comparison(name: str, operator: str, value: Any) -> str:
    field_name = name.removesuffix(TIMESTAMP_DESIGNATOR)
    query_field = FIELDS.get(field_name)
    if query_field is None:
        raise ValueError(f"{field_name!r} is not a field. The fields are: {', '.join(FIELDS)}.")
    if name != field_name and query_field.type is not FieldType.DATE:
        raise ValueError(
            f'{field_name!r} is not a date field. Only a date field can have the "{TIMESTAMP_DESIGNATOR}" suffix.'
        )
    if operator.removeprefix("C") == "~":
        raise ValueError(
            'TrueSearch does not use regular expressions. To find text anywhere in a value, use "rin". To compare '
            'the start or the end, use "^" or "$".'
        )

    caseless = operator.startswith("C")
    base = operator.removeprefix("C")
    if base not in OPERATORS[query_field.type] or (caseless and query_field.type not in _CASELESS):
        raise ValueError(
            f"The {field_name!r} field does not use {operator!r}. Use one of: {_operator_list(query_field.type)}."
        )

    modifiers = "cd" if caseless else ""
    if base in ("in", "nin"):
        if not isinstance(value, (list, tuple)) or not value:
            raise ValueError(f"For {operator!r}, the value of {field_name!r} must be a list with one or more values.")

        single = "=" if base == "in" else "!="
        return _join(
            [_single(field_name, query_field, single, item, modifiers) for item in value],
            "||" if base == "in" else "&&",
        )

    return _single(field_name, query_field, base, value, modifiers)


def _single(field_name: str, query_field: QueryField, operator: str, value: Any, modifiers: str) -> str:
    attribute = query_field.attribute
    match query_field.type:
        case FieldType.TEXT | FieldType.TAGS:
            if not isinstance(value, str):
                raise ValueError(f"The value of {field_name!r} must be a string.")

            operators = TEXT_OPERATORS if query_field.type is FieldType.TEXT else TAG_OPERATORS
            comparison, pattern = operators[operator]
            return f'{attribute} {comparison} "{pattern.format(value.translate(_SPECIAL))}"{modifiers}'
        case FieldType.NUMBER:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"The value of {field_name!r} must be an integer.")

            return f"{attribute} {COMPARISONS[operator]} {value}"
        case FieldType.DATE:
            return f"{attribute} {COMPARISONS[operator]} $time.iso({_iso(field_name, value)})"
        case FieldType.CHOICE:
            if not isinstance(value, str) or value not in query_field.choices:
                raise ValueError(f"The value of {field_name!r} must be one of: {', '.join(query_field.choices)}.")

            return f'{attribute} {COMPARISONS[operator]} "{query_field.choices[value]}"'

    raise AssertionError(query_field.type)


def _iso(field_name: str, value: Any) -> str:
    """
    Convert a date to the form that `$time.iso` reads: UTC, a year of four digits, and whole seconds. truesearchd
    compares whole seconds. A date without a time zone is UTC.
    """
    if not isinstance(value, str):
        raise ValueError(f"The value of {field_name!r} must be an ISO-8601 date string.")

    try:
        when = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{value!r} is not an ISO-8601 date string.") from None

    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)

    try:
        when = when.astimezone(timezone.utc)
    except OverflowError:
        raise ValueError(f"{value!r} is not between the years 1 and 9999 in UTC.") from None

    return when.replace(tzinfo=None, microsecond=0).isoformat() + "Z"


def _operator_list(field_type: FieldType) -> str:
    return ", ".join(f"`{operator}`" for operator in OPERATORS[field_type])

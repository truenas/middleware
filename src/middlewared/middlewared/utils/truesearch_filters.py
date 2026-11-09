"""
This module is the translation layer of `truesearch.query`.

A user writes filters with simple field names, for example `name` or `size`. truesearchd reads a macOS Spotlight
query. This module converts the filters into that query.

Two tables control the translation:

* `FIELDS` gives the Spotlight attribute of each field, and the type of its values.
* `TEXT_OPERATORS` and the other operator tables give the Spotlight form of each operator.

To add a field, add a row to `FIELDS`. The API documentation of the filters comes from the same tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import enum
from typing import Any

from middlewared.api.base.validators.filters import TIMESTAMP_DESIGNATOR

# The maximum number of entries that one search finds. This is RIX_MAX_RESULTS of truesearchd.
MAX_RESULTS = 1000
# A Spotlight query uses these characters as wildcards and quotes. A value must escape them.
_SPECIAL = str.maketrans({char: "\\" + char for char in '\\"*?'})


class FieldType(enum.Enum):
    TEXT = "Text"
    TAGS = "Tag"
    NUMBER = "Number"
    DATE = "Date"
    CHOICE = "Choice"


# The Spotlight comparison of each text operator, and the pattern around the value. `*` matches any text.
TEXT_OPERATORS = {
    "=": ("==", "{}"),
    "!=": ("!=", "{}"),
    "^": ("==", "{}*"),
    "!^": ("!=", "{}*"),
    "$": ("==", "*{}"),
    "!$": ("!=", "*{}"),
    "rin": ("==", "*{}*"),
    "rnin": ("!=", "*{}*"),
}
# A tag must agree with the full value.
TAG_OPERATORS = {
    "rin": ("==", "{}"),
    "rnin": ("!=", "{}"),
}
# The Spotlight comparison of each number, date or choice operator.
COMPARISONS = {"=": "==", "!=": "!=", ">": ">", ">=": ">=", "<": "<", "<=": "<="}
# The operators of each type. `in` and `nin` compare with each value of a list.
OPERATORS = {
    FieldType.TEXT: tuple(TEXT_OPERATORS) + ("in", "nin"),
    FieldType.TAGS: tuple(TAG_OPERATORS),
    FieldType.NUMBER: tuple(COMPARISONS) + ("in", "nin"),
    FieldType.DATE: tuple(COMPARISONS),
    FieldType.CHOICE: ("=", "!=", "in", "nin"),
}
# These types also take each operator with `C` before it. `C` ignores case and accents.
_CASELESS = frozenset({FieldType.TEXT, FieldType.TAGS})


@dataclass(frozen=True, slots=True)
class Choice:
    """One value of a choice field: the Spotlight value that it stands for, and its documentation."""

    value: str
    description: str


@dataclass(frozen=True, slots=True)
class QueryField:
    """One field of `truesearch.query`: its Spotlight attribute, the type of its values, and its documentation."""

    attribute: str
    type: FieldType
    description: str
    choices: dict[str, Choice] = field(default_factory=dict)


FIELDS: dict[str, QueryField] = {
    "name": QueryField("kMDItemFSName", FieldType.TEXT, "The name of the file or directory."),
    "type": QueryField(
        "kMDItemContentTypeTree",
        FieldType.CHOICE,
        "The type of the entry.",
        {
            "DIRECTORY": Choice("public.directory", "A directory. A macOS package is also a directory."),
            "FILE": Choice("public.data", "A file. FIFOs, sockets, and device files are also files here."),
            "SYMLINK": Choice("public.symlink", "A symbolic link. TrueSearch does not follow links."),
        },
    ),
    "size": QueryField(
        "kMDItemFSSize",
        FieldType.NUMBER,
        "The size in bytes. For a directory, ZFS gives the number of entries in the directory.",
    ),
    "uid": QueryField("kMDItemFSOwnerUserID", FieldType.NUMBER, "The user ID of the owner."),
    "gid": QueryField("kMDItemFSOwnerGroupID", FieldType.NUMBER, "The group ID of the owner group."),
    "mtime": QueryField("kMDItemFSContentChangeDate", FieldType.DATE, "The last time that the data changed."),
    "btime": QueryField("kMDItemFSCreationDate", FieldType.DATE, "The time that the file was created."),
    "atime": QueryField("kMDItemLastUsedDate", FieldType.DATE, "The last time that the file was read."),
    "macos_kind": QueryField(
        "kMDItemKind",
        FieldType.CHOICE,
        "The kind of file that the macOS Finder shows. TrueSearch gets the kind from the file name extension, not "
        "from the content. A file with an unknown extension has no kind.",
        {
            "FOLDER": Choice("Folder", "A directory that is not a macOS package."),
            "PDF": Choice("PDF", "A PDF document with the `.pdf` extension."),
            "IMAGE": Choice("Image", "An image, for example `.jpg`, `.png`, `.gif`, `.heic`, `.tiff`, or `.psd`."),
            "MOVIE": Choice("Movie", "A video, for example `.mp4`, `.mov`, `.mkv`, or `.avi`."),
            "AUDIO": Choice("Audio", "An audio file, for example `.mp3`, `.m4a`, `.flac`, or `.wav`."),
            "TEXT": Choice("Text", "A text file, for example `.txt`, `.md`, `.csv`, `.html`, or source code."),
            "DOCUMENT": Choice(
                "Document",
                "A word processor document: `.doc`, `.docx`, `.odt`, `.rtf`, or `.pages`.",
            ),
            "SPREADSHEET": Choice("Spreadsheet", "A spreadsheet: `.xls`, `.xlsx`, `.ods`, `.numbers`, or `.csv`."),
            "PRESENTATION": Choice("Presentation", "A presentation: `.ppt`, `.pptx`, `.odp`, or `.key`."),
            "ARCHIVE": Choice("Archive", "An archive: `.zip`, `.7z`, `.rar`, `.tar`, `.gz`, or `.xz`."),
            "APPLICATION": Choice(
                "Application",
                "A macOS application with the `.app` extension, or a disk image. A Windows program "
                "with the `.exe` extension is not an application here.",
            ),
            "DISK_IMAGE": Choice(
                "Disk Image",
                "A disk image: a `.dmg` file, or a `.sparsebundle` or `.backupbundle` package.",
            ),
            "PACKAGE": Choice(
                "Package",
                "A macOS package. A package is a directory that a Mac shows as one item, for example "
                "`.app`, `.sparsebundle`, `.photoslibrary`, or `.rtfd`.",
            ),
            "FONT": Choice("Font", "A font: `.ttf`, `.otf`, `.woff`, or `.woff2`."),
            "CONTACT": Choice("Contact", "A contact card with the `.vcf` extension."),
            "MAIL": Choice("Mail", "An email message with the `.eml` extension."),
        },
    ),
    "tags": QueryField("kMDItemUserTags", FieldType.TAGS, "The tags that a macOS user set on the file in the Finder."),
    "comment": QueryField(
        "kMDItemFinderComment",
        FieldType.TEXT,
        "The comment that a macOS user set on the file in the Finder.",
    ),
}


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

            return f'{attribute} {COMPARISONS[operator]} "{query_field.choices[value].value}"'

    raise AssertionError(query_field.type)


def _iso(field_name: str, value: Any) -> str:
    """Convert a date to the form that `$time.iso` reads: UTC, in seconds. A date without a time zone is UTC."""
    if not isinstance(value, str):
        raise ValueError(f"The value of {field_name!r} must be an ISO-8601 date string.")

    try:
        when = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{value!r} is not an ISO-8601 date string.") from None

    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)

    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _operator_list(field_type: FieldType) -> str:
    return ", ".join(f"`{operator}`" for operator in OPERATORS[field_type])


# The documentation of the operators of each type.
_TYPE_DOC = {
    FieldType.TEXT: [
        "`=` and `!=` compare the full value.",
        "`^` and `!^` compare the start of the value.",
        "`$` and `!$` compare the end of the value.",
        "`rin` finds the text anywhere in the value. `rnin` finds values that do not contain the text.",
        "`in` and `nin` compare the full value with each value in a list.",
        "Put `C` before an operator to ignore case and accents, for example `C=` or `Crin`.",
    ],
    FieldType.TAGS: [
        "`rin` finds files that have the tag. `rnin` finds files that do not have the tag.",
        "The tag must agree with the full value. Put `C` before the operator to ignore case and accents.",
    ],
    FieldType.NUMBER: [
        "`=`, `!=`, `>`, `>=`, `<`, and `<=` compare the value.",
        "`in` and `nin` compare the value with each value in a list.",
    ],
    FieldType.DATE: [
        "`=`, `!=`, `>`, `>=`, `<`, and `<=` compare the date.",
        "Write the date as an ISO-8601 string, for example `2026-01-31T09:00:00`. A date without a time zone is "
        "in UTC. As in other query methods, you can add `.$date` to the field name.",
    ],
    FieldType.CHOICE: [
        "`=` and `!=` compare the value.",
        "`in` and `nin` compare the value with each value in a list.",
    ],
}


def filters_doc() -> str:
    """The API documentation of `query-filters`, made from `FIELDS` and the operator tables."""
    lines = [
        "The filters that select the files and directories. Write each filter as `[field, operator, value]`, as in "
        "other query methods. All filters must match. To match one of several filters, use "
        '`["OR", [filter, filter]]`. If you give no filters, the query returns all files and directories in `path` '
        "and its subdirectories.",
        "",
        "TrueSearch uses the index that answers macOS Spotlight searches through SMB. Middleware converts the filters "
        "into a Spotlight query. Thus, a query gets the same results as a Spotlight search from a Mac. TrueSearch "
        "does not use regular expressions.",
    ]
    for field_type, sentences in _TYPE_DOC.items():
        names = [name for name, query_field in FIELDS.items() if query_field.type is field_type]
        if not names:
            continue

        lines += ["", f"{field_type.value} fields:", ""]
        for name in names:
            lines.append(f"* `{name}`: {FIELDS[name].description}")
            lines += [f"  * `{choice}`: {value.description}" for choice, value in FIELDS[name].choices.items()]
        lines += ["", f"{field_type.value} fields use these operators:", ""]
        lines += [f"* {sentence}" for sentence in sentences]

    lines += [
        "",
        "Examples:",
        "",
        '* `[["name", "Crin", "report"]]` finds names that contain "report", in any case.',
        '* `[["macos_kind", "=", "PDF"], ["size", ">", 1048576]]` finds PDF documents that are larger than 1 MiB.',
        '* `[["OR", [["name", "$", ".jpg"], ["name", "$", ".png"]]]]` finds names that end with `.jpg` or `.png`.',
        '* `[["mtime", ">=", "2026-01-01T00:00:00"]]` finds files that changed in 2026 or later.',
        '* `[["tags", "rin", "Important"]]` finds files that have the tag "Important".',
    ]
    return "\n".join(lines)

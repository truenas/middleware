"""
Tests of the translation layer of `truesearch.query`. A user writes filters with simple field names. These tests
check the Spotlight query that middleware sends to truesearchd for each filter. The API never shows this query.
"""

import pytest

from middlewared.utils.truesearch_filters import FIELDS, filters_doc, spotlight_query


@pytest.mark.parametrize(
    "filters,query",
    [
        # No filters match all entries.
        ([], 'kMDItemFSName == "*"'),
        # Text operators.
        ([["name", "=", "notes.txt"]], 'kMDItemFSName == "notes.txt"'),
        ([["name", "!=", "notes.txt"]], 'kMDItemFSName != "notes.txt"'),
        ([["name", "^", "rep"]], 'kMDItemFSName == "rep*"'),
        ([["name", "!^", "rep"]], 'kMDItemFSName != "rep*"'),
        ([["name", "$", ".pdf"]], 'kMDItemFSName == "*.pdf"'),
        ([["name", "!$", ".txt"]], 'kMDItemFSName != "*.txt"'),
        ([["name", "rin", "port"]], 'kMDItemFSName == "*port*"'),
        ([["name", "rnin", "tmp"]], 'kMDItemFSName != "*tmp*"'),
        ([["name", "in", ["a", "b"]]], '(kMDItemFSName == "a" || kMDItemFSName == "b")'),
        ([["name", "nin", ["a", "b"]]], '(kMDItemFSName != "a" && kMDItemFSName != "b")'),
        # `C` ignores case and accents.
        ([["name", "C=", "NOTES.TXT"]], 'kMDItemFSName == "NOTES.TXT"cd'),
        ([["name", "Crin", "report"]], 'kMDItemFSName == "*report*"cd'),
        ([["comment", "C^", "quarterly"]], 'kMDItemFinderComment == "quarterly*"cd'),
        # Wildcards and quotes in a value are escaped. They match only themselves.
        ([["name", "=", 'a"b\\c*d?']], 'kMDItemFSName == "a\\"b\\\\c\\*d\\?"'),
        # Tags.
        ([["tags", "rin", "Red"]], 'kMDItemUserTags == "Red"'),
        ([["tags", "Crnin", "work"]], 'kMDItemUserTags != "work"cd'),
        # Numbers.
        ([["size", ">", 1000]], "kMDItemFSSize > 1000"),
        ([["size", "<=", 10]], "kMDItemFSSize <= 10"),
        ([["uid", "in", [0, 1000]]], "(kMDItemFSOwnerUserID == 0 || kMDItemFSOwnerUserID == 1000)"),
        ([["gid", "!=", 5]], "kMDItemFSOwnerGroupID != 5"),
        # Dates. A date without a time zone is UTC.
        (
            [["mtime.$date", ">=", "2026-01-01T00:00:00"]],
            "kMDItemFSContentChangeDate >= $time.iso(2026-01-01T00:00:00Z)",
        ),
        ([["btime", "<", "2026-01-01T02:30:00+02:00"]], "kMDItemFSCreationDate < $time.iso(2026-01-01T00:30:00Z)"),
        ([["atime", "=", "2026-01-01"]], "kMDItemLastUsedDate == $time.iso(2026-01-01T00:00:00Z)"),
        # Choices.
        ([["type", "=", "DIRECTORY"]], 'kMDItemContentTypeTree == "public.directory"'),
        ([["type", "=", "SYMLINK"]], 'kMDItemContentTypeTree == "public.symlink"'),
        ([["type", "!=", "FILE"]], 'kMDItemContentTypeTree != "public.data"'),
        ([["macos_kind", "=", "DISK_IMAGE"]], 'kMDItemKind == "Disk Image"'),
        ([["macos_kind", "nin", ["IMAGE", "PDF"]]], '(kMDItemKind != "Image" && kMDItemKind != "PDF")'),
        # All filters of a list must match. "OR" matches one of its filters.
        ([["size", ">", 1], ["name", "$", ".md"]], '(kMDItemFSSize > 1 && kMDItemFSName == "*.md")'),
        (
            [["OR", [["name", "=", "a"], [["macos_kind", "=", "PDF"], ["size", ">", 10]]]]],
            '(kMDItemFSName == "a" || (kMDItemKind == "PDF" && kMDItemFSSize > 10))',
        ),
        (
            [["OR", [["OR", [["size", "=", 1], ["size", "=", 2]]], ["name", "=", "a"]]]],
            '((kMDItemFSSize == 1 || kMDItemFSSize == 2) || kMDItemFSName == "a")',
        ),
    ],
)
def test_spotlight_query(filters, query):
    assert spotlight_query(filters) == query


@pytest.mark.parametrize(
    "filters,why",
    [
        ([["kind", "=", "PDF"]], "not a field"),
        ([["name", ">", "a"]], "does not use"),
        ([["size", "C=", 1]], "does not use"),
        ([["tags", "=", "Red"]], "does not use"),
        ([["macos_kind", "C=", "PDF"]], "does not use"),
        ([["name", "~", "rep.*"]], "regular expressions"),
        ([["name", "C~", "rep"]], "regular expressions"),
        ([["size", "=", "10"]], "must be an integer"),
        ([["size", "=", True]], "must be an integer"),
        ([["name", "=", 1]], "must be a string"),
        ([["macos_kind", "=", "PHOTO"]], "must be one of"),
        ([["type", "=", ["FILE"]]], "must be one of"),
        ([["name", "in", []]], "one or more values"),
        ([["name", "in", "a"]], "one or more values"),
        ([["mtime", ">", "yesterday"]], "not an ISO-8601 date"),
        ([["mtime", ">", 1700000000]], "ISO-8601 date string"),
        ([["name.$date", ">", "2026-01-01"]], "not a date field"),
        ([["OR", []]], '"OR" must have'),
        ([["name", "="]], "is not a filter"),
        (["name"], "is not a filter"),
    ],
)
def test_spotlight_query_refuses(filters, why):
    with pytest.raises(ValueError, match=why):
        spotlight_query(filters)


@pytest.mark.parametrize("name", ["type", "macos_kind"])
def test_every_choice_is_a_value_of_its_attribute(name):
    field = FIELDS[name]
    for choice, value in field.choices.items():
        assert spotlight_query([[name, "=", choice]]) == f'{field.attribute} == "{value.value}"'


def test_filters_doc_documents_every_field_and_choice():
    doc = filters_doc()
    for name, field in FIELDS.items():
        assert f"* `{name}`: {field.description}" in doc
        for choice, value in field.choices.items():
            assert f"  * `{choice}`: {value.description}" in doc

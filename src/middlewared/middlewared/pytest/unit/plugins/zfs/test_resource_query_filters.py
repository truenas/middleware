import enum
import errno
from unittest.mock import patch

import pytest

from middlewared.api.current import ZFSResourceQueryExtra, ZFSResourceQueryOptions
from middlewared.plugins.zfs.property_management import PROPERTY_TEMPLATES
from middlewared.plugins.zfs.resource_query import (
    build_private_query,
    identity_paths,
    referenced_properties,
)
from middlewared.service_exception import ValidationError

DEFAULT_PROPERTY_NAMES = sorted(prop.name.lower() for prop in PROPERTY_TEMPLATES.default)


@pytest.mark.parametrize(
    "filters,expected",
    [
        ([], None),
        ([["type", "=", "VOLUME"]], None),
        ([["id", "!=", "tank/a"]], None),
        ([["id", "~", "tank/a"]], None),
        ([["id", "=", 1]], None),
        ([["id", "in", ["tank/a", 2]]], None),
        ([["OR", [["id", "=", "tank/a"]]]], None),
        ([["id", "=", "tank/a"]], ["tank/a"]),
        ([["name", "=", "tank/a"]], ["tank/a"]),
        ([["id", "in", ["tank/a", "tank/b"]]], ["tank/a", "tank/b"]),
        ([["name", "in", ["tank/a", "tank/a"]]], ["tank/a"]),
        ([["id", "in", []]], []),
        ([["id", "=", "tank/a@snap"]], []),
        ([["id", "in", ["tank/a@snap", "tank/b"]]], ["tank/b"]),
        ([["id", "=", "tank/a"], ["name", "=", "tank/b"]], ["tank/a"]),
        ([["type", "=", "VOLUME"], ["id", "=", "tank/a"]], ["tank/a"]),
    ],
)
def test_identity_paths(filters, expected):
    assert identity_paths(filters) == expected


@pytest.mark.parametrize(
    "filters,select,names,needs_source",
    [
        ([], [], set(), False),
        ([["type", "=", "VOLUME"]], [], set(), False),
        ([["properties.compression", "=", "lz4"]], [], {"compression"}, False),
        ([["properties.compression.value", "=", "lz4"]], [], {"compression"}, False),
        ([["properties.compression.raw", "=", "lz4"]], [], {"compression"}, False),
        ([["properties.compression.source", "=", "LOCAL"]], [], {"compression"}, True),
        ([["properties.compression.source.type", "=", "LOCAL"]], [], {"compression"}, True),
        ([["properties.compression.source.value", "=", "x"]], [], {"compression"}, True),
        (
            [["OR", [["properties.atime.value", "=", "on"], ["properties.dedup.value", "=", "on"]]]],
            [],
            {"atime", "dedup"},
            False,
        ),
        ([], ["properties.quota.value"], {"quota"}, False),
        ([], [["properties.quota.source.type", "quota_source"]], {"quota"}, True),
        ([], ["name"], set(), False),
    ],
)
def test_referenced_properties(filters, select, names, needs_source):
    assert referenced_properties(filters, select) == (names, needs_source)


class FakeZFSProperty(enum.Enum):
    """`truenas_pylibzfs` is mocked out in unit tests, so the real name lookup has to be stood in for."""

    COMPRESSION = 1
    QUOTA = 2


def test_referenced_properties_accepts_a_known_name():
    with patch("middlewared.plugins.zfs.resource_query.ZFSProperty", FakeZFSProperty):
        assert referenced_properties([["properties.compression.value", "=", "lz4"]], []) == ({"compression"}, False)


def test_referenced_properties_rejects_unknown_name():
    with patch("middlewared.plugins.zfs.resource_query.ZFSProperty", FakeZFSProperty):
        with pytest.raises(ValidationError) as ve:
            referenced_properties([["properties.nosuchprop.value", "=", 1]], [])
    assert ve.value.attribute == "zfs.resource.query.filters"
    assert ve.value.errno == errno.EINVAL


def options(**extra):
    return ZFSResourceQueryOptions(extra=ZFSResourceQueryExtra(**extra))


def test_build_private_query_default_scope_is_pool_roots():
    data = build_private_query([], options())
    assert data.paths == []
    assert data.get_children is False
    assert data.max_depth == 0
    assert data.allow_internal_paths is True


def test_build_private_query_carve_out_ignores_declared_scope():
    data = build_private_query([["id", "=", "tank/a"]], options(paths=["tank/b"], get_children=True, max_depth=3))
    assert data.paths == ["tank/a"]
    assert data.get_children is False
    assert data.max_depth == 0
    assert data.allow_internal_paths is False


def test_build_private_query_nothing_can_match():
    assert build_private_query([["id", "in", []]], options()) is None
    assert build_private_query([["id", "=", "tank/a@snap"]], options()) is None


def test_build_private_query_merges_referenced_properties():
    assert build_private_query([], options()).properties == []
    assert build_private_query([], options(properties=None)).properties is None
    assert build_private_query([], options(properties=["quota"])).properties == ["quota"]

    filters = [["properties.compression.value", "=", "lz4"]]
    assert build_private_query(filters, options(properties=None)).properties == ["compression"]
    assert build_private_query(filters, options()).properties == sorted({*DEFAULT_PROPERTY_NAMES, "compression"})
    assert build_private_query(filters, options(properties=["quota"])).properties == ["compression", "quota"]


def test_build_private_query_source_follows_the_filter():
    assert build_private_query([], options()).get_source is False
    assert build_private_query([["properties.quota.source.type", "=", "LOCAL"]], options()).get_source is True
    assert build_private_query([], options(get_source=True)).get_source is True

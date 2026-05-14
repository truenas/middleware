import pytest

from middlewared.plugins.account_.constants import CONTAINER_ROOT_UID, IDMAP_COUNT
from middlewared.plugins.container.lifecycle import _build_idmap_items, _resolve_target
from middlewared.service_exception import CallError


def _as_tuples(items):
    return [(i.start, i.target, i.count) for i in items]


def test__resolve_target_direct():
    assert _resolve_target(3000, 'DIRECT') == (3000, 3000)


def test__resolve_target_explicit():
    assert _resolve_target(3000, 5) == (5, 3000)


def test__build_idmap_items_empty():
    # No passthroughs: one filler covers the entire in-range space.
    items = _build_idmap_items([])
    assert _as_tuples(items) == [(0, CONTAINER_ROOT_UID, IDMAP_COUNT)]


def test__build_idmap_items_single_in_range_middle():
    items = _build_idmap_items([(100, 3000)])
    assert _as_tuples(items) == [
        (0, CONTAINER_ROOT_UID, 100),
        (100, 3000, 1),
        (101, CONTAINER_ROOT_UID + 101, IDMAP_COUNT - 101),
    ]


def test__build_idmap_items_at_slot_zero():
    items = _build_idmap_items([(0, 4000)])
    assert _as_tuples(items) == [
        (0, 4000, 1),
        (1, CONTAINER_ROOT_UID + 1, IDMAP_COUNT - 1),
    ]


def test__build_idmap_items_at_last_in_range_slot():
    last = IDMAP_COUNT - 1
    items = _build_idmap_items([(last, 5000)])
    assert _as_tuples(items) == [
        (0, CONTAINER_ROOT_UID, last),
        (last, 5000, 1),
    ]


def test__build_idmap_items_multiple_in_range_sorts_and_fills_gaps():
    items = _build_idmap_items([(50, 7000), (10, 6000)])
    assert _as_tuples(items) == [
        (0, CONTAINER_ROOT_UID, 10),
        (10, 6000, 1),
        (11, CONTAINER_ROOT_UID + 11, 39),
        (50, 7000, 1),
        (51, CONTAINER_ROOT_UID + 51, IDMAP_COUNT - 51),
    ]


def test__build_idmap_items_out_of_range_appended():
    high = IDMAP_COUNT + 5
    items = _build_idmap_items([(high, 9000)])
    assert _as_tuples(items) == [
        (0, CONTAINER_ROOT_UID, IDMAP_COUNT),
        (high, 9000, 1),
    ]


def test__build_idmap_items_mixed_in_and_out_of_range():
    high = IDMAP_COUNT + 100
    items = _build_idmap_items([(high, 9000), (5, 4000)])
    assert _as_tuples(items) == [
        (0, CONTAINER_ROOT_UID, 5),
        (5, 4000, 1),
        (6, CONTAINER_ROOT_UID + 6, IDMAP_COUNT - 6),
        (high, 9000, 1),
    ]


def test__build_idmap_items_duplicate_in_range_rejected():
    with pytest.raises(CallError, match='Duplicate container-side id 42'):
        _build_idmap_items([(42, 3000), (42, 4000)])


def test__build_idmap_items_duplicate_out_of_range_rejected():
    high = IDMAP_COUNT + 1
    with pytest.raises(CallError, match=f'Duplicate container-side id {high}'):
        _build_idmap_items([(high, 3000), (high, 4000)])

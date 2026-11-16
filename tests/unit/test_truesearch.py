"""
Tests of the pure functions of the TrueSearch plugin. The tests that go through the API are in
tests/api2/test_truesearch.py.
"""

from datetime import datetime, timezone

import pytest
from truesearch_client.config import TargetRow
from truesearch_client.control import IndexerStatus, IndexerTarget, UnindexedTarget

from middlewared.api.current import TruesearchQuery
import middlewared.plugins.truesearch as truesearch_plugin
from middlewared.plugins.truesearch import DatasetInfo, TruesearchService, beneath, carried_rows


@pytest.mark.parametrize(
    "options",
    [
        {"limit": 0},
        {"limit": 1001},
        {"offset": 5},
        {"get": True},
        {"select": ["name"]},
        {"order_by": ["size"]},
        {"count": True},
    ],
)
def test_query_options_take_only_a_limit(options):
    with pytest.raises(ValueError):
        TruesearchQuery.model_validate({"path": "/mnt/tank/data", "query-options": options})


@pytest.mark.parametrize(
    "directory,datasets,result",
    [
        ("/mnt/tank/users", ["tank"], {"/mnt/tank/users"}),
        ("/mnt/tank/users/alex", ["tank", "tank/users"], {"/mnt/tank/users/alex"}),
        # Each dataset beneath a share directory is indexed too.
        (
            "/mnt/tank/users",
            ["tank", "tank/users", "tank/users/alice", "tank/users/alice/books", "tank/users/bob"],
            {"/mnt/tank/users", "/mnt/tank/users/alice", "/mnt/tank/users/alice/books", "/mnt/tank/users/bob"},
        ),
        # The share directory does not have to be the mountpoint of a dataset.
        ("/mnt/tank/shares", ["tank", "tank/shares/media"], {"/mnt/tank/shares", "/mnt/tank/shares/media"}),
        # A directory in no dataset gives nothing.
        ("/mnt/gone/x", ["tank"], set()),
    ],
)
def test_processed_directories_for_directory(directory, datasets, result):
    mountpoints = {f"/mnt/{name}": DatasetInfo(name, "1") for name in datasets}
    assert TruesearchService(None)._processed_directories_for_directory(mountpoints, directory) == result


def test_a_time_that_datetime_cannot_hold_has_no_value():
    # touch -d '9999-12-31 23:59:59' west of UTC gives a time after the year 9999.
    assert truesearch_plugin._time(253_402_329_599, 0) is None


def test_a_time_is_not_rounded_into_the_next_second():
    assert truesearch_plugin._time(1_794_142_012, 999_999_600) == datetime.fromtimestamp(
        1_794_142_012, tz=timezone.utc
    ).replace(microsecond=999_999)


@pytest.mark.parametrize(
    "activity,state,reason",
    [
        ("idle", "READY", None),
        ("starting", "INDEXING", None),
        ("queued", "INDEXING", None),
        ("building", "INDEXING", None),
        ("full pass", "INDEXING", None),
        ("directory pass", "INDEXING", None),
        ("rebuild", "INDEXING", None),
        ("an activity of a later indexer", "INDEXING", None),
        ("waiting for its root", "UNAVAILABLE", "The dataset is not mounted at '/mnt/tank/one'."),
    ],
)
def test_each_activity_has_a_state(activity, state, reason):
    target = IndexerTarget(
        live=5,
        activity=activity,
        watching=False,
        last_full=0,
        last_dirs=0,
        queued=0,
        size=4096,
    )
    indexer = IndexerStatus(index_bytes=0, free_bytes=0, space_low=False, targets={"ds1": target})
    row = TargetRow(id="ds1", dataset="tank/one", root="/mnt/tank/one")
    status = truesearch_plugin._dataset_status(row, indexer, set())
    assert (status.state, status.reason) == (state, reason)


def test_a_row_that_the_indexer_does_not_run_is_unavailable():
    # The row is held, in conflict, or refused. The indexer gives no counts for it.
    targets = {"ds1": UnindexedTarget(why="its root is gone")}
    indexer = IndexerStatus(index_bytes=0, free_bytes=None, space_low=False, targets=targets)
    row = TargetRow(id="ds1", dataset="tank/one", root="/mnt/tank/one")
    status = truesearch_plugin._dataset_status(row, indexer, set())
    assert (status.state, status.reason, status.entries, status.index_size) == (
        "UNAVAILABLE",
        "its root is gone",
        None,
        None,
    )


@pytest.mark.parametrize(
    "path,top,result",
    [
        ("/mnt/tank/a", "/mnt/tank/a", True),
        ("/mnt/tank/a/b", "/mnt/tank/a", True),
        ("/mnt/tank/ab", "/mnt/tank/a", False),
        ("/mnt/tank", "/mnt/tank/a", False),
    ],
)
def test_beneath(path, top, result):
    assert beneath(path, top) is result


OLD = [
    TargetRow(id="ds1", dataset="gone/a", root="/mnt/gone/a"),
    TargetRow(id="ds2", dataset="gone/b", root="/mnt/gone/b", exclude=("tm",)),
    TargetRow(id="ds3", dataset="tank/c", root="/mnt/tank/c"),
    TargetRow(id="ds4", dataset="gone/d", root="/mnt/gone/d", enabled=False),
    TargetRow(id="ds5", dataset="", root="/mnt/gone/e"),
]


def test_carried_rows_keep_the_shared_rows_of_a_pool_that_is_not_imported():
    shares = {"/mnt/gone/a/team", "/mnt/gone", "/mnt/tank/c"}
    assert carried_rows(OLD, [], {"tank"}, shares) == [
        TargetRow(id="ds1", dataset="gone/a", root="/mnt/gone/a", enabled=False),
        TargetRow(id="ds2", dataset="gone/b", root="/mnt/gone/b", enabled=False),
        TargetRow(id="ds4", dataset="gone/d", root="/mnt/gone/d", enabled=False),
    ]


def test_carried_rows_leave_a_row_without_a_share():
    assert carried_rows(OLD, [], {"tank"}, {"/mnt/gone/a"}) == [
        TargetRow(id="ds1", dataset="gone/a", root="/mnt/gone/a", enabled=False),
    ]


def test_carried_rows_leave_a_row_the_datasets_hold():
    rows = [
        TargetRow(id="ds1", dataset="gone/a", root="/mnt/gone/x"),
        TargetRow(id="ds9", dataset="gone/x", root="/mnt/gone/b"),
    ]
    assert carried_rows(OLD, rows, set(), {"/mnt/gone"}) == [
        TargetRow(id="ds4", dataset="gone/d", root="/mnt/gone/d", enabled=False),
    ]

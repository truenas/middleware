import os
import re

import pytest

from middlewared.utils.truesearch import (
    ID_MAX,
    TargetRow,
    _unquote_debug,
    beneath,
    carried_rows,
    daemons_holding,
    devices_of,
    parse_indexer_status,
    parse_served_ids,
    quote,
    render_config,
    rendered_rows,
    target_id,
    unquote,
    wait_released,
)

PATHS = [
    "/mnt/tank/projects",
    "/mnt/tank/Archive, 2025 ",
    '/mnt/tank/"q"\\x',
    "/mnt/tank/a\nb\tc\rd",
    "/mnt/tank/\x01\x7f",
    "/mnt/tank/Résumé",
    b"/mnt/tank/\xff".decode(errors="surrogateescape"),
]


@pytest.mark.parametrize(
    "path,quoted",
    [
        ("/mnt/tank/projects", '"/mnt/tank/projects"'),
        ("/mnt/tank/Archive, 2025 ", '"/mnt/tank/Archive, 2025 "'),
        ('/mnt/tank/"q"\\x', '"/mnt/tank/\\"q\\"\\\\x"'),
        ("/mnt/tank/a\nb\tc\rd", '"/mnt/tank/a\\nb\\tc\\rd"'),
        ("/mnt/tank/\x01\x7f", '"/mnt/tank/\\x01\\x7f"'),
        ("/mnt/tank/Résumé", '"/mnt/tank/Résumé"'),
        (b"/mnt/tank/\xff".decode(errors="surrogateescape"), '"/mnt/tank/\\xff"'),
    ],
)
def test_quote(path, quoted):
    assert quote(path) == quoted


def test_target_id_is_the_guid():
    assert target_id("tank/projects", "16091380264393486042") == "ds16091380264393486042"


@pytest.mark.parametrize("dataset", ["tank/my projects", "tank/my_projects", ".tank/x", "t/" + "x" * 300])
def test_target_id_without_a_guid(dataset):
    id_ = target_id(dataset, None)
    assert re.fullmatch(r"[A-Za-z0-9_.-]+", id_)
    assert not id_.startswith(".")
    assert len(id_) <= ID_MAX


def test_target_ids_without_a_guid_differ():
    assert target_id("tank/my projects", None) != target_id("tank/my_projects", None)


def test_render_config():
    text = render_config(
        [
            TargetRow(id="ds2", dataset="tank/b", root="/mnt/tank/b", exclude=("tm", "old, scratch")),
            TargetRow(id="ds1", dataset="tank/a", root="/mnt/tank/a/shares"),
        ]
    )
    assert text == (
        "# Written by middleware. Changes here are lost.\n"
        "\n"
        "# tank/a\n"
        '[target "ds1"]\n'
        'root = "/mnt/tank/a/shares"\n'
        "\n"
        "# tank/b\n"
        '[target "ds2"]\n'
        'root = "/mnt/tank/b"\n'
        'exclude = "tm", "old, scratch"\n'
    )
    assert [row.id for row in rendered_rows(text)] == ["ds1", "ds2"]


def test_render_config_of_a_disabled_row():
    text = render_config([TargetRow(id="ds1", dataset="tank/a", root="/mnt/tank/a", enabled=False)])
    assert text.endswith('[target "ds1"]\nroot = "/mnt/tank/a"\nenabled = no\n')


def test_rendered_rows_of_no_rows():
    assert rendered_rows(render_config([])) == []


@pytest.mark.parametrize("path", PATHS)
def test_unquote_reads_quote_back(path):
    assert unquote(quote(path)) == path


@pytest.mark.parametrize("text", ["/mnt/tank", '"/mnt/tank', '"a"b"', '"a\\"', '"\\q"', '"\\x4"', '"\\xzz"'])
def test_unquote_refuses_what_quote_does_not_write(text):
    assert unquote(text) is None


def test_rendered_rows_read_the_rows_back():
    rows = [TargetRow(id=f"ds{i}", dataset=f"tank/d{i}", root=path, enabled=i % 2 == 0) for i, path in enumerate(PATHS)]
    assert rendered_rows(render_config(rows)) == rows


def test_rendered_rows_leave_out_the_exclusions_and_keep_a_root_that_does_not_read_back():
    text = '[target "ds1"]\nroot = "/mnt/tank/a\nexclude = "tm"\n'
    assert rendered_rows(text) == [TargetRow(id="ds1", dataset="", root="")]


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


def test_devices_of_leave_out_a_path_that_is_gone(tmp_path):
    assert devices_of([str(tmp_path), str(tmp_path / "gone")]) == {os.stat(tmp_path).st_dev}


def test_wait_released_of_no_device():
    assert daemons_holding(set()) is False
    assert wait_released(set(), timeout=0) is True


# The shape of real answers, from a run of both daemons with these rows.
INDEXER_STATUS = "\n".join(
    [
        "ok",
        "targets=2 draining=false index_bytes=98304 free_bytes=1698759966720 space_low=false",
        "target ds1 root=/mnt/tank/share one live=2 tombstones=0 commit=13 activity=idle watching=true events=0 "
        "last_full=1794142012 last_dirs=0 map=0 queued=0 size=94208 ahead=false fsid=00151c7996f7c081",
        "target ds2 root=/mnt/tank/missing live=0 tombstones=0 commit=0 activity=held watching=false events=0 "
        "last_full=0 last_dirs=0 map=0 queued=0 size=0 ahead=unknown fsid=unknown "
        'held="the root /mnt/tank/missing cannot be opened: ENOENT: No such file or directory (os error 2)"',
        r"target ds3 root=\"/mnt/tank/bad\" live=0 tombstones=0 commit=0 activity=held watching=false events=0 "
        "last_full=0 last_dirs=0 map=0 queued=0 size=0 ahead=unknown fsid=unknown "
        r'held="[target \"ds3\"] exclude = \"\\\"../x\\\"\" is not a value it takes"',
        "target ds4 root=/mnt/tank/data live=40 tombstones=1 commit=9 activity=full pass watching=true events=7 "
        "last_full=1794000000 last_dirs=1794100000 map=1 queued=2 size=4096 ahead=false fsid=0011223344556677",
    ]
)

DAEMON_STATUS = "\n".join(
    [
        "ok",
        "handles=0 identities=0 draining=false",
        "target ds1 root=/mnt/tank/share one format=1 fold=1 kinds=1 live=2 tombstones=0 commit=13 "
        "fsid=00151c7996f7c081",
        "target ds2 root=/mnt/tank/missing served=false "
        'why="ds2: anchor /mnt/tank/missing: ENOENT: No such file or directory (os error 2)"',
        "target ds4 root=/mnt/tank/data format=1 fold=1 kinds=1 live=40 tombstones=1 commit=9 fsid=0011223344556677",
    ]
)


def test_parse_indexer_status():
    status = parse_indexer_status(INDEXER_STATUS)
    assert (status.index_bytes, status.free_bytes, status.space_low) == (98304, 1698759966720, False)
    assert sorted(status.targets) == ["ds1", "ds2", "ds3", "ds4"]

    one = status.targets["ds1"]
    assert (one.live, one.activity, one.watching) == (2, "idle", True)
    assert (one.last_full, one.last_dirs, one.queued, one.size, one.held) == (1794142012, 0, 0, 94208, None)

    assert status.targets["ds2"].activity == "held"
    assert status.targets["ds2"].held == (
        "the root /mnt/tank/missing cannot be opened: ENOENT: No such file or directory (os error 2)"
    )
    assert status.targets["ds3"].held == '[target "ds3"] exclude = "\\"../x\\"" is not a value it takes'

    four = status.targets["ds4"]
    assert (four.activity, four.queued, four.last_dirs) == ("full pass", 2, 1794100000)


@pytest.mark.parametrize("answer", ["draining", "", "ok", "invalid status"])
def test_parse_indexer_status_of_another_answer(answer):
    with pytest.raises(ValueError):
        parse_indexer_status(answer)


def test_parse_served_ids():
    assert parse_served_ids(DAEMON_STATUS) == {"ds1", "ds4"}


def test_unquote_debug():
    assert _unquote_debug('"a \\"b\\" \\\\ \\n \\t \\u{1f600} \\u{zz}"') == 'a "b" \\ \n \t \U0001f600 \\u{zz}'
    assert _unquote_debug("unquoted") == "unquoted"

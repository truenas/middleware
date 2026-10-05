import pytest

from middlewared.plugins.rsync.utils import quote_extra_args
from middlewared.pytest.unit.helpers import load_migration

parse_legacy = load_migration('27.0/2026-10-05_12-00_rsync_extra_json_list').parse_legacy


@pytest.mark.parametrize(
    "extra,expected",
    [
        (['--rsync-path="sudo rsync"'], ["'--rsync-path=sudo rsync'"]),
        (["--rsync-path='sudo rsync'"], ["'--rsync-path=sudo rsync'"]),
        (['--rsync-path="/usr/bin/env rsync"'], ["'--rsync-path=/usr/bin/env rsync'"]),
        (['--exclude="my file"'], ["'--exclude=my file'"]),
        (
            ['--rsync-path="sudo rsync"', '--exclude="my file"'],
            ["'--rsync-path=sudo rsync'", "'--exclude=my file'"],
        ),
    ],
)
def test_quoted_value_is_regrouped(extra, expected):
    """The user's quotes group the value; they must not survive into the argument itself."""
    assert quote_extra_args(extra) == expected


@pytest.mark.parametrize(
    "extra,expected",
    [
        (["-avz"], ["-avz"]),
        (["--rsync-path=/usr/bin/rsync"], ["--rsync-path=/usr/bin/rsync"]),
        (['--rsync-path="/usr/bin/rsync"'], ["--rsync-path=/usr/bin/rsync"]),
        (["--exclude", "excluded_file"], ["--exclude", "excluded_file"]),
        ([], []),
    ],
)
def test_options_needing_no_grouping(extra, expected):
    assert quote_extra_args(extra) == expected


def test_glob_is_quoted_against_the_local_shell():
    """The command line is run through a shell, so patterns rsync expands itself must stay unexpanded."""
    assert quote_extra_args(["--bwlimit=1000", "--exclude", "*.tmp"]) == [
        "--bwlimit=1000",
        "--exclude",
        "'*.tmp'",
    ]


@pytest.mark.parametrize(
    "extra,expected",
    [
        (['"'], ["'\"'"]),
        (["--exclude", '"unclosed'], ["--exclude", "'\"unclosed'"]),
        (
            ['--rsync-path="sudo rsync"', "--exclude=foo\\"],
            ["'--rsync-path=sudo rsync'", "'--exclude=foo\\'"],
        ),
    ],
)
def test_unbalanced_quotes_are_passed_through(extra, expected):
    """A misconfigured value stored by an older version has no grouping to resolve, so it is left alone."""
    assert quote_extra_args(extra) == expected


def test_a_backslash_escaped_space_survives_quoting():
    """One stored parameter becomes one argument."""
    assert quote_extra_args([r"--rsync-path=sudo\ /usr/bin/rsync"]) == [
        "'--rsync-path=sudo /usr/bin/rsync'"
    ]


@pytest.mark.parametrize(
    "stored,expected",
    [
        ("", []),
        (None, []),
        ("-avz", ["-avz"]),
        ("--exclude .snapshot --delete", ["--exclude", ".snapshot", "--delete"]),
        ('--rsync-path="sudo rsync"', ['--rsync-path="sudo rsync"']),
        ("--bwlimit=1000 --exclude *.tmp", ["--bwlimit=1000", "--exclude", "*.tmp"]),
        ("--exclude=foo\\", ["--exclude=foo\\"]),
    ],
)
def test_migration_finds_the_old_boundaries(stored, expected):
    """A parameter the old reader handled moves over unchanged."""
    assert parse_legacy(stored) == expected


def test_migration_restores_a_grouping_the_old_reader_lost():
    """The boundary split eats the escape, so the migration puts the grouping back."""
    stored = r"--rsync-path=sudo\ /usr/bin/rsync"
    assert parse_legacy(stored) == ["'--rsync-path=sudo /usr/bin/rsync'"]
    assert quote_extra_args(parse_legacy(stored)) == ["'--rsync-path=sudo /usr/bin/rsync'"]


def test_migration_cannot_repair_an_already_eroded_value():
    """A row that already lost its escape reads as two parameters. The owner enters it again."""
    assert parse_legacy("--rsync-path=sudo /usr/bin/rsync") == [
        "--rsync-path=sudo",
        "/usr/bin/rsync",
    ]


@pytest.mark.parametrize(
    "stored,expected_argv",
    [
        ("-avz", ["-avz"]),
        ("--exclude .snapshot --delete", ["--exclude", ".snapshot", "--delete"]),
        ('--rsync-path="sudo rsync"', ["'--rsync-path=sudo rsync'"]),
        ("--bwlimit=1000 --exclude *.tmp", ["--bwlimit=1000", "--exclude", "'*.tmp'"]),
        ("--exclude=foo\\", ["'--exclude=foo\\'"]),
    ],
)
def test_migrated_row_builds_the_same_command_line(stored, expected_argv):
    """The upgrade does not change the command an existing task runs."""
    assert quote_extra_args(parse_legacy(stored)) == expected_argv

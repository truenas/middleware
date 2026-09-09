import pytest

from middlewared.plugins.rsync_.utils import quote_extra_args


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

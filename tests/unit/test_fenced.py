import pytest

from fenced.main import parse_ed
from fenced.utils import load_disks_impl


@pytest.mark.parametrize(
    "exclude,expected",
    [
        ("sda,", ("sda",)),
        ("", ()),
        ("sda,sdb", ("sda", "sdb")),
        ("sda, sdb", ("sda", "sdb")),
        ("sda,sdb      sdc", ("sda", "sdb", "sdc")),
        ("sda sdb sdc", ("sda", "sdb", "sdc")),
        ("sda     sdb  sdc", ("sda", "sdb", "sdc")),
    ],
)
def test_parse_ed(exclude, expected):
    assert parse_ed(exclude) == expected


@pytest.mark.parametrize("exclude", [tuple(), ("sda"), ("sda,sdb")])
def test_load_disks(exclude):
    """We need to make sure that fenced always enumerates
    a list of disks."""
    disks = load_disks_impl(exclude)
    assert disks
    for disk in exclude:
        assert disk not in disks

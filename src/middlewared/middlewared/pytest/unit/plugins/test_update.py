import pytest

from middlewared.plugins.update import CompareTrainsResult, compare_trains


@pytest.mark.parametrize("t1,t2,result", [
    ("TrueNAS-SCALE-Angelfish", "TrueNAS-SCALE-Bluefin", CompareTrainsResult.MAJOR_UPGRADE),
    ("TrueNAS-SCALE-Bluefin", "TrueNAS-SCALE-Angelfish", CompareTrainsResult.MAJOR_DOWNGRADE),
    ("TrueNAS-SCALE-Angelfish-Nightlies", "TrueNAS-SCALE-Bluefin-Nightlies", CompareTrainsResult.MAJOR_UPGRADE),
    ("TrueNAS-SCALE-Bluefin-Nightlies", "TrueNAS-SCALE-Angelfish-Nightlies", CompareTrainsResult.MAJOR_DOWNGRADE),

    ("TrueNAS-SCALE-Angelfish", "TrueNAS-SCALE-Angelfish-Nightlies", CompareTrainsResult.NIGHTLY_UPGRADE),
    ("TrueNAS-SCALE-Angelfish", "TrueNAS-SCALE-Bluefin-Nightlies", CompareTrainsResult.NIGHTLY_UPGRADE),
    ("TrueNAS-SCALE-Angelfish-Nightlies", "TrueNAS-SCALE-Angelfish", CompareTrainsResult.NIGHTLY_DOWNGRADE),
    ("TrueNAS-SCALE-Angelfish-Nightlies", "TrueNAS-SCALE-Bluefin", CompareTrainsResult.NIGHTLY_DOWNGRADE),

    ("TrueNAS-SCALE-Angelfish", "TrueNAS-SCALE-Angelfish", None),
])
def test__compare_trains(t1, t2, result):
    assert compare_trains(t1, t2) == result

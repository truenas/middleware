import pytest

from middlewared.plugins.update import CompareTrainsResult, compare_trains


@pytest.mark.parametrize("t1,t2,result", [
    ("FreeNAS-11.2-STABLE", "FreeNAS-9.10-STABLE", CompareTrainsResult.MAJOR_DOWNGRADE),
    ("FreeNAS-9.10-STABLE", "FreeNAS-11.2-STABLE", CompareTrainsResult.MAJOR_UPGRADE),

    ("FreeNAS-11.2-STABLE", "FreeNAS-11-Nightlies", CompareTrainsResult.NIGHTLY_UPGRADE),
    ("FreeNAS-11-Nightlies", "FreeNAS-11.2-STABLE", CompareTrainsResult.NIGHTLY_DOWNGRADE),
    ("FreeNAS-11-STABLE", "FreeNAS-11-Nightlies", CompareTrainsResult.NIGHTLY_UPGRADE),
    ("FreeNAS-11-Nightlies", "FreeNAS-11-STABLE", CompareTrainsResult.NIGHTLY_DOWNGRADE),
    ("FreeNAS-11.2-STABLE", "FreeNAS-11-Nightlies-SDK", CompareTrainsResult.NIGHTLY_UPGRADE),
    ("FreeNAS-11-Nightlies-SDK", "FreeNAS-11.2-STABLE", CompareTrainsResult.NIGHTLY_DOWNGRADE),

    ("FreeNAS-11-STABLE", "FreeNAS-11.2-STABLE", CompareTrainsResult.MINOR_UPGRADE),
    ("FreeNAS-11.1-STABLE", "FreeNAS-11.2-STABLE", CompareTrainsResult.MINOR_UPGRADE),
    ("FreeNAS-11.2-STABLE", "FreeNAS-11.1-STABLE", CompareTrainsResult.MINOR_DOWNGRADE),
    ("FreeNAS-11.2-STABLE", "FreeNAS-11-STABLE", CompareTrainsResult.MINOR_DOWNGRADE),

    ("FreeNAS-9.10-STABLE", "FreeNAS-9.10-STABLE", None),
    ("FreeNAS-11-Nightlies", "FreeNAS-11-Nightlies", None),
])
def test__compare_trains(t1, t2, result):
    assert compare_trains(t1, t2) == result

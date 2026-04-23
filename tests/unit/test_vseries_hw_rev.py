from types import SimpleNamespace
from unittest.mock import patch

import pytest

from middlewared.plugins.failover_ import detect_utils


# (raw DMI, expected is_vseries_v2_interconnect())
# True  => new topology (internal X710 LACP bond)
# False => old topology (external 10 GbE cable)
# Unreadable / malformed DMI defaults to True (assume >= 2.0) and also
# fires the vseries_unstamped_spd alert (see that alert source — it
# calls parse_major_minor_version directly to detect the same condition).
CASES = [
    # Valid — old topology (< 2.0)
    ('1.0', False),
    ('1.1', False),
    ('1.99', False),
    # Valid — new topology (>= 2.0)
    ('2.0', True),
    ('2.1', True),
    ('3.0', True),
    ('9.9', True),
    ('10.0', True),          # multi-digit major allowed
    ('25.1', True),
    ('99.99', True),
    # Whitespace tolerated around the value
    (' 2.0 ', True),
    # Invalid — all default to new topology (True)
    ('0.9', True),           # leading-zero major rejected
    ('01.0', True),          # leading-zero major rejected
    ('0100', True),          # no dot — Gigabyte packed form is NOT accepted
    ('2.0.0', True),         # must be exactly <major>.<minor>
    ('2.0-beta', True),      # no suffix
    ('1', True),             # needs the dot + minor
    ('1.', True),            # needs at least one digit after dot
    ('', True),
    (None, True),
    ('bogus', True),
    ('..', True),
]


@pytest.mark.parametrize('raw,expected', CASES)
def test_is_vseries_v2_interconnect(raw, expected):
    with patch.object(
        detect_utils, 'parse_dmi',
        return_value=SimpleNamespace(system_version=raw),
    ):
        assert detect_utils.is_vseries_v2_interconnect() is expected

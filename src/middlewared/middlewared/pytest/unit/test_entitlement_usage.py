"""Keep the usage probes in step with the policy they report against"""

from middlewared.plugins.truenas.entitlement_usage import PROBES
from middlewared.utils.entitlements import POLICY


def test_probes_cover_policy():
    assert set(PROBES) == set(POLICY)

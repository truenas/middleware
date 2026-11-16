import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call, non_enterprise_test


# ----------------------------------------------------------------------------
# Entitlement gate: this only runs where the system lacks the ZFSTIER
# entitlement. Where it has it, the tier_pool fixture is already exercising the
# entitled path.
# ----------------------------------------------------------------------------


@non_enterprise_test
def test_update_requires_zfstier_entitlement(zfstier_entitlement):
    with pytest.raises(CallError) as exc:
        call("zfs.tier.update", {"enabled": True})
    # zfs.tier.update raises CallError(ent.message) verbatim, so the denial the
    # caller sees must be the engine's own wording, not merely license-ish text.
    assert zfstier_entitlement["message"] in str(exc.value)

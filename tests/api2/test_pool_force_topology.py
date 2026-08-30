import pytest
from truenas_api_client import ValidationErrors

from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.utils import call

# Four names that cannot exist. `pool.create` validates topology before it looks at disks --
# `_process_topology` runs `verrors.check()` on `_validate_topology`'s result before
# `disk.check_disks_availability` -- so the gate is reachable without consuming a disk and no
# pool is created. Four, because RAIDZ2's minimum is 4 and a shorter list would add a
# min-disks error alongside the one being asserted.
FAKE_DISKS = ["nosuchdisk0", "nosuchdisk1", "nosuchdisk2", "nosuchdisk3"]


def test_force_topology_rejected_when_support_entitled():
    """The gate fires through `pool.create`, not just through `_validate_topology`."""
    with entitled("SUPPORT"):
        with pytest.raises(ValidationErrors) as ve:
            call(
                "pool.create",
                {
                    "name": "test_force_topology",
                    "topology": {"data": [{"type": "RAIDZ2", "disks": FAKE_DISKS}]},
                    "force_topology": True,
                },
                job=True,
            )

    assert [(e.attribute, e.errmsg) for e in ve.value.errors] == [
        (
            "pool_create.force_topology",
            "Bypassing pool topology validation is not permitted on systems with a support entitlement.",
        )
    ]

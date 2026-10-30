"""
Opt-in fixtures for test_267_iscsi_ua_pr_per_nexus.py.

None of these are autouse -- this directory is shared with
test_261_iscsi_cmd.py and test_266_iscsi_lio_alua.py, and an autouse
fixture here would run for every test collected in the directory
regardless of whether it's ours. See UA_PR_TEST_SUITE_PLAN.md.
"""

from dataclasses import dataclass
import random
import string

from assets.websocket.iscsi import alua_enabled, initiator, portal, target, target_extent_associate, zvol_extent
from assets.websocket.pool import zvol as zvol_dataset
from auto_config import ha, pool_name
from iscsi_ua_pr_utils import (
    BASENAME,
    CLIENT_IQN,
    LABEL_B_IQN,
    SERVICE_NAME,
    lio_mode,
    set_ua_intlck_ctrl,
    wait_for_alua_settle,
)
from middlewared.test.integration.utils import call
import pytest

LUN_ZVOL_MB = 20


@dataclass
class ConfiguredLun:
    iqn: str
    zvol: str
    ext_name: str
    size_mb: int
    target_id: int


@pytest.fixture
def configured_lun(request):
    """LIO-mode target+zvol-extent+LUN, freshly created for one test.

    The initiator group is named (not open) and whitelists every identity
    label open_topology() can produce (CLIENT_IQN for "A", LABEL_B_IQN for
    "B") -- a named group is required for iscsi.global.update({'alua':
    True}) to succeed later (see lio_alua_configured), so this same setup
    serves both ALUA and non-ALUA tests without being recreated.

    Indirect-parametrize with an emulate_ua_intlck_ctrl mode name
    ("CLEAR"/"NO_CLEAR"/"ESTABLISH_UA") to have it set on the backstore
    right after the extent is created -- the kernel only accepts writes to
    that attribute while the device has zero exports
    (target_core_configfs.c's emulate_ua_intlck_ctrl_store()), so it must
    happen here, before target_extent_associate() below, not afterward.
    No restore is needed: this backstore is fresh per test and gets torn
    down entirely at the end of it.

    iscsi.extent.create()'s do_create never triggers a service reload (only
    do_update/do_delete do) -- so the LIO configfs render that actually
    creates the backstore's directory hasn't happened yet at this point.
    Force one explicitly so the directory exists (with export_count still
    0) before writing the attribute; target_extent_associate() below does
    its own reload afterward to export the LUN, which doesn't touch this
    attribute again (_update_storage_object_attrs() only re-writes wwn/
    identity, not emulate_ua_intlck_ctrl).
    """
    ua_intlck_mode = getattr(request, "param", None)
    rnd = "".join(random.choices(string.digits, k=6))
    zvol_name = f"ds_ua_pr_{rnd}"
    zvol_path = f"{pool_name}/{zvol_name}"
    ext_name = f"ext_ua_pr_{rnd}"
    tgt_name = f"tgt-ua-pr-{rnd}"

    with lio_mode():
        with initiator(initiators=[CLIENT_IQN, LABEL_B_IQN]) as init_config:
            with portal() as portal_config:
                with zvol_dataset(zvol_path, LUN_ZVOL_MB):
                    with zvol_extent(zvol_path, ext_name) as extent_config:
                        if ua_intlck_mode is not None:
                            call("service.control", "RELOAD", SERVICE_NAME, job=True)
                            set_ua_intlck_ctrl(ext_name, ua_intlck_mode)
                        with target(
                            tgt_name,
                            [{"portal": portal_config["id"], "initiator": init_config["id"]}],
                        ) as tgt_config:
                            with target_extent_associate(tgt_config["id"], extent_config["id"]):
                                yield ConfiguredLun(
                                    iqn=f"{BASENAME}:{tgt_config['name']}",
                                    zvol=zvol_path,
                                    ext_name=ext_name,
                                    size_mb=LUN_ZVOL_MB,
                                    target_id=tgt_config["id"],
                                )


@pytest.fixture
def lio_alua_configured(configured_lun):
    """As configured_lun, with ALUA additionally enabled. Requires HA
    hardware -- skips (rather than asserting) if unavailable, since this
    fixture also backs module-level tests that must stay collectible
    (and simply not run) on non-HA systems."""
    if not ha:
        pytest.skip("ALUA transition tests require HA hardware")
    assert call("failover.config")["disabled"] is False
    with alua_enabled():
        wait_for_alua_settle()
        yield configured_lun

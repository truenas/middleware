"""Tier field exposure on sharing.smb.query and sharing.nfs.query, plus
integration of the SMB conf `shadow:no_dataset_traversal` setting that's
triggered by tiering being enabled.

Implementation under test:
  - src/middlewared/middlewared/service/sharing_service.py:33-135
    (include_tier_info → bulk_get_tier_info → tier injection in extend)
  - src/middlewared/middlewared/plugins/smb.py:237, 278, 751
  - src/middlewared/middlewared/plugins/nfs.py:421
  - src/middlewared/middlewared/plugins/smb_/util_smbconf.py:701-702
  - src/middlewared/middlewared/api/v27_0_0/smb.py:761-840
  - src/middlewared/middlewared/api/v27_0_0/nfs.py:180-191
"""

import contextlib
import time

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.nfs import nfs_share
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call, ssh


@contextlib.contextmanager
def _temporarily_disabled():
    original = call("zfs.tier.config")["enabled"]
    if not original:
        yield
        return
    call("zfs.tier.update", {"enabled": False})
    try:
        yield
    finally:
        call("zfs.tier.update", {"enabled": original})


@contextlib.contextmanager
def _temporarily_enabled():
    original = call("zfs.tier.config")["enabled"]
    if original:
        yield
        return
    call("zfs.tier.update", {"enabled": True})
    try:
        yield
    finally:
        call("zfs.tier.update", {"enabled": original})


def _unique(name):
    return f"{name}{time.monotonic_ns() % 1_000_000_000}"


# ----------------------------------------------------------------------------
# sharing.smb.query tier field
# ----------------------------------------------------------------------------


def test_sharing_smb_query_returns_tier_field(tier_ds_performance):
    """Shares on tier-capable datasets carry a TierInfo `tier` field."""
    name = _unique("tier_smb_perf")
    with smb_share(f"/mnt/{tier_ds_performance}", name) as share:
        rows = call("sharing.smb.query", [["id", "=", share["id"]]])
        assert len(rows) == 1
        assert "tier" in rows[0]
        assert rows[0]["tier"] is not None
        assert rows[0]["tier"]["tier_type"] == "PERFORMANCE"


def test_sharing_smb_query_tier_reflects_regular(tier_ds_regular):
    name = _unique("tier_smb_reg")
    with smb_share(f"/mnt/{tier_ds_regular}", name) as share:
        rows = call("sharing.smb.query", [["id", "=", share["id"]]])
        assert rows[0]["tier"] is not None
        assert rows[0]["tier"]["tier_type"] == "REGULAR"


def test_sharing_smb_query_tier_is_null_when_globally_disabled(tier_ds_performance):
    """When zfs.tier.config.enabled is False, sharing.smb.query tier is null."""
    name = _unique("tier_smb_disabled")
    with smb_share(f"/mnt/{tier_ds_performance}", name) as share:
        with _temporarily_disabled():
            rows = call("sharing.smb.query", [["id", "=", share["id"]]])
            assert rows[0]["tier"] is None


def test_sharing_smb_query_tier_is_null_on_pool_without_special(tier_pool):
    """Default test pool has no SPECIAL vdev — share tier is null."""
    with dataset("smb_no_special_tier") as ds:
        name = _unique("smb_no_sp")
        with smb_share(f"/mnt/{ds}", name) as share:
            rows = call("sharing.smb.query", [["id", "=", share["id"]]])
            assert rows[0]["tier"] is None


def test_sharing_smb_update_rejects_tier_field(tier_ds):
    """SMB share update with a `tier` key is rejected: tier is Excluded()
    on SharingSMBUpdateArgs (api/v27_0_0/smb.py:840)."""
    name = _unique("smb_update_tier")
    with smb_share(f"/mnt/{tier_ds}", name) as share:
        with pytest.raises(ValidationErrors):
            call(
                "sharing.smb.update",
                share["id"],
                {"tier": {"tier_type": "PERFORMANCE", "tier_job": None}},
            )


# ----------------------------------------------------------------------------
# sharing.nfs.query tier field
# ----------------------------------------------------------------------------


def test_sharing_nfs_query_returns_tier_field(tier_ds_performance):
    with nfs_share(tier_ds_performance) as share:
        rows = call("sharing.nfs.query", [["id", "=", share["id"]]])
        assert len(rows) == 1
        assert "tier" in rows[0]
        assert rows[0]["tier"] is not None
        assert rows[0]["tier"]["tier_type"] == "PERFORMANCE"


def test_sharing_nfs_query_tier_reflects_regular(tier_ds_regular):
    with nfs_share(tier_ds_regular) as share:
        rows = call("sharing.nfs.query", [["id", "=", share["id"]]])
        assert rows[0]["tier"] is not None
        assert rows[0]["tier"]["tier_type"] == "REGULAR"


def test_sharing_nfs_query_tier_is_null_when_globally_disabled(tier_ds_performance):
    with nfs_share(tier_ds_performance) as share:
        with _temporarily_disabled():
            rows = call("sharing.nfs.query", [["id", "=", share["id"]]])
            assert rows[0]["tier"] is None


def test_sharing_nfs_query_tier_is_null_on_pool_without_special(tier_pool):
    with dataset("nfs_no_special_tier") as ds:
        with nfs_share(ds) as share:
            rows = call("sharing.nfs.query", [["id", "=", share["id"]]])
            assert rows[0]["tier"] is None


def test_sharing_nfs_update_rejects_tier_field(tier_ds):
    """tier is Excluded() on the NFS update model (api/v27_0_0/nfs.py:191)."""
    with nfs_share(tier_ds) as share:
        with pytest.raises(ValidationErrors):
            call(
                "sharing.nfs.update",
                share["id"],
                {"tier": {"tier_type": "PERFORMANCE", "tier_job": None}},
            )


# ----------------------------------------------------------------------------
# SMB smb.conf: shadow:no_dataset_traversal set when tiering is enabled.
# This is the live integration counterpart of the unit test in
# tests/unit/test_smb_service.py:487-505.
# ----------------------------------------------------------------------------


def _testparm_value(parameter):
    """Read a parameter from the live smb.conf (registry). testparm renders
    booleans as 'Yes'/'No' or 'True'/'False' depending on version; values are
    returned verbatim."""
    out = ssh(
        f"testparm -s --section-name=global --parameter-name='{parameter}' 2>/dev/null"
    ).strip()
    return out


def _is_truthy(value):
    return value.lower() in ("yes", "true")


def _is_falsy_or_absent(value):
    return value.lower() in ("", "no", "false")


def test_smb_conf_shadow_no_dataset_traversal_when_tiering_enabled(tier_ds):
    """A running SMB server with tiering enabled should have
    shadow:no_dataset_traversal set to a truthy value in its loaded config."""
    name = _unique("smb_conf_enabled")
    with smb_share(f"/mnt/{tier_ds}", name):
        # smb_share already started cifs; force etc.generate so the registry
        # reflects the current zfs.tier state.
        call("etc.generate", "smb")
        ssh("smbcontrol smbd reload-config 2>/dev/null || true")
        value = _testparm_value("shadow:no_dataset_traversal")
        assert _is_truthy(value), (
            f"Expected shadow:no_dataset_traversal=Yes/True when tiering enabled, got: {value!r}"
        )


def test_smb_conf_shadow_no_dataset_traversal_absent_when_disabled(tier_ds):
    """When tiering is disabled, the option should not be set (or set to False)."""
    name = _unique("smb_conf_disabled")
    with smb_share(f"/mnt/{tier_ds}", name):
        with _temporarily_disabled():
            call("etc.generate", "smb")
            ssh("smbcontrol smbd reload-config 2>/dev/null || true")
            value = _testparm_value("shadow:no_dataset_traversal")
            assert _is_falsy_or_absent(value), (
                f"Expected shadow:no_dataset_traversal absent/No/False when tiering disabled, got: {value!r}"
            )

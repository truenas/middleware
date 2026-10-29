import logging
from types import SimpleNamespace

import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import SharingNFSEntry
from middlewared.plugins.nfs_.share_validate import validate_expose_snapshots
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ServiceContext
from middlewared.service_exception import ValidationErrors

NOT_ROOT = "/mnt/tank/ds: export path is not the root directory of a dataset."


@pytest.mark.parametrize(
    "old_expose,dataset_root,expected",
    [
        (True, True, []),
        (False, True, ["license"]),
        (None, False, ["license", NOT_ROOT]),
    ],
)
@pytest.mark.asyncio
async def test_expose_snapshots_license_gates_only_turning_it_on(old_expose, dataset_root, expected):
    m = Middleware()
    install_entitlements_for_column(m, LicenseFeature.NFS_SNAPSHOT, "CE+L")
    m["filesystem.statfs"] = lambda path: SimpleNamespace(dest=path if dataset_root else "/mnt/tank")
    data = SharingNFSEntry.model_construct(path="/mnt/tank/ds", expose_snapshots=True)
    old = (
        None
        if old_expose is None
        else SharingNFSEntry.model_construct(path="/mnt/tank/ds", expose_snapshots=old_expose)
    )

    verrors = ValidationErrors()
    await validate_expose_snapshots(
        ServiceContext(m, logging.getLogger("test")), data, "sharingnfs_update", verrors, old
    )

    messages = [e.errmsg for e in verrors.errors]
    assert [msg if msg == NOT_ROOT else "license" for msg in messages] == expected
    assert all(e.attribute == "sharingnfs_update.expose_snapshots" for e in verrors.errors)

from types import SimpleNamespace

import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.system_advanced.config import SystemAdvancedConfigServicePart
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service_exception import ValidationErrors


@pytest.mark.parametrize(
    "stored_passwd,kmip_uid,refused",
    [
        ("", None, True),
        ("", "uid", False),
        ("old", None, False),
    ],
)
@pytest.mark.asyncio
async def test_sed_passwd_license_gates_only_a_first_password(stored_passwd, kmip_uid, refused):
    m = Middleware()
    install_entitlements_for_column(m, LicenseFeature.SED, "HW")
    m["datastore.config"] = lambda *args: {"sed_passwd": stored_passwd, "kmip_uid": kmip_uid}
    part = SimpleNamespace(middleware=m, _datastore="system.advanced", _datastore_prefix="adv_")
    verrors = ValidationErrors()
    await SystemAdvancedConfigServicePart._validate_sed_passwd(part, verrors, "secret")
    assert [e.attribute for e in verrors.errors] == (["sed_passwd"] if refused else [])

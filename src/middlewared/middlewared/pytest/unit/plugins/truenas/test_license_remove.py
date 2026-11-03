from unittest.mock import Mock, patch

import pytest
from truenas_pylicensed import LicenseType
from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.truenas.license import TrueNASLicenseService
from middlewared.pytest.unit.entitlements import make_license
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.parametrize(
    "license_,removed",
    [
        (make_license(feature_names=(LicenseFeature.TNC_SUB,), type_=LicenseType.COMMUNITY), True),
        (make_license(feature_names=(), type_=LicenseType.COMMUNITY), False),
        (make_license(feature_names=(LicenseFeature.TNC_SUB,), type_=LicenseType.COMMERCIAL), False),
        (None, False),
    ],
)
def test_remove_tnc_license_gate(license_, removed):
    middleware = Middleware()
    middleware.run_coroutine = Mock(side_effect=lambda coro, wait: coro.close())
    service = create_service(middleware, TrueNASLicenseService)

    with (
        patch.object(service, "info_private", return_value=license_),
        patch("middlewared.plugins.truenas.license.remove_license") as remove_license,
    ):
        service.remove_tnc_license()

    assert remove_license.called is removed

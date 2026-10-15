from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from truenas_pylicensed import LicenseError
from truenas_pylicensed.features import LicenseFeature

from middlewared.auth import TruenasNodeSessionManagerCredentials
from middlewared.plugins.truenas.license import TrueNASLicenseService
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service_exception import CallError, ValidationError
from middlewared.utils.entitlements import POLICY

MODULE = "middlewared.plugins.truenas.license"
USER = SimpleNamespace(authenticated_credentials=Mock())
NODE = SimpleNamespace(authenticated_credentials=TruenasNodeSessionManagerCredentials())
OLDER = "2026-01-01T00:00:00+00:00"
NEWER = "2026-06-01T00:00:00Z"


def status(*, code=LicenseError.OK, test=False, issued_at=NEWER, features=()):
    valid = code == LicenseError.OK
    return SimpleNamespace(
        code=code,
        valid=valid,
        test=test,
        id="7c1e4b0a" if valid else None,
        issued_at=issued_at if valid else None,
        type=None,
        error=None if valid else code.name,
        has_feature=lambda name: valid and name in features,
    )


NO_LICENSE = status(code=LicenseError.NO_LICENSE)


def license_service(*, failover_status="MASTER", in_progress=False, vip_rows=()):
    middleware = Middleware()
    middleware["failover.status"] = Mock(return_value=failover_status)
    middleware["failover.in_progress"] = Mock(return_value=in_progress)
    middleware["interface.query"] = Mock(return_value=list(vip_rows))
    middleware["system.is_ha_capable"] = Mock(return_value=True)
    return create_service(middleware, TrueNASLicenseService)


def upload(service, app, delivered, installed=NO_LICENSE, rolled_back=None):
    @contextmanager
    def upload_license(pem):
        try:
            yield delivered
        except Exception:
            if rolled_back is not None:
                rolled_back.append(True)
            raise

    with (
        patch(f"{MODULE}.verify", Mock(return_value=installed)),
        patch(f"{MODULE}.get_license", Mock(return_value=None)),
        patch(f"{MODULE}.snapshot", Mock(return_value=dict.fromkeys(POLICY, False))),
        patch(f"{MODULE}.upload_license", upload_license),
    ):
        service.upload(app, "-----BEGIN LICENSE-----")


@pytest.mark.parametrize(
    "app,failover_status,in_progress,refused",
    [
        (USER, "BACKUP", False, True),
        (USER, "MASTER", True, True),
        (NODE, "BACKUP", True, False),
        (None, "BACKUP", True, False),
    ],
)
def test_role_refusals_exempt_node_and_internal_callers(app, failover_status, in_progress, refused):
    """Sync to Peer and controller replacement install on the standby under the node credential."""
    service = license_service(failover_status=failover_status, in_progress=in_progress)
    if refused:
        with pytest.raises(CallError):
            upload(service, app, status())
    else:
        upload(service, app, status())


@pytest.mark.parametrize("vip_rows", [[], [{"id": 1}]])
def test_ha_loss_keys_on_vip_rows_and_rolls_back(vip_rows):
    """A non-HA license on a pair with VIPs would collapse it; the refused file must not stay installed."""
    service = license_service(vip_rows=vip_rows)
    rolled_back = []
    if vip_rows:
        with pytest.raises(ValidationError, match="HA license is required"):
            upload(service, None, status(), rolled_back=rolled_back)
        assert rolled_back == [True]
    else:
        upload(service, None, status(), rolled_back=rolled_back)
        assert rolled_back == []


@pytest.mark.parametrize(
    "app,installed,refused",
    [
        (NODE, status(issued_at=NEWER), True),
        (None, status(issued_at=NEWER), True),
        (USER, status(issued_at=NEWER), False),
        (None, NO_LICENSE, False),
        (None, status(issued_at=NEWER, test=True), False),
    ],
    ids=["node", "tnc", "user", "installed-legacy", "installed-test"],
)
def test_older_license_refused_only_for_unattended_callers(app, installed, refused):
    """A stale standby or TNC re-sending an old PEM must not undo a newer license; a user may downgrade."""
    service = license_service()
    if refused:
        with pytest.raises(ValidationError, match="older"):
            upload(service, app, status(issued_at=OLDER), installed)
    else:
        upload(service, app, status(issued_at=OLDER), installed)


@pytest.mark.parametrize("app,refused", [(NODE, True), (None, True), (USER, False)])
def test_test_license_over_production_refused_for_unattended_callers(app, refused):
    """A test license skips the serial check, so propagation must not put one over production."""
    service = license_service()
    delivered = status(test=True, issued_at=NEWER)
    installed = status(issued_at=OLDER)
    if refused:
        with pytest.raises(ValidationError, match="test license"):
            upload(service, app, delivered, installed)
    else:
        upload(service, app, delivered, installed)


@pytest.mark.parametrize(
    "code", [LicenseError.DAEMON_UNAVAILABLE, LicenseError.DAEMON_ERROR, LicenseError.INTERNAL_ERROR]
)
def test_daemon_error_is_not_a_rejection(code):
    """The TNC heartbeat never retries a PEM refused with a ValidationError."""
    with pytest.raises(CallError):
        upload(license_service(), None, status(code=code))


@pytest.mark.parametrize(
    "installed,vip_rows,blob_has_ha,error",
    [
        (status(), [], True, ValidationError),
        (status(code=LicenseError.DAEMON_UNAVAILABLE), [], True, CallError),
        (NO_LICENSE, [{"id": 1}], False, ValidationError),
    ],
    ids=["valid-v2-installed", "daemon-error", "ha-loss"],
)
def test_install_legacy_refusals(installed, vip_rows, blob_has_ha, error):
    """A legacy blob must not delete a valid v2 license, nor be read as installable during a daemon blip,
    nor drop HA from a pair with VIPs."""
    service = license_service(vip_rows=vip_rows)
    parsed = SimpleNamespace(model="M40", has_feature=lambda name: blob_has_ha and name == LicenseFeature.HA)
    with (
        patch(f"{MODULE}.parse_legacy_license", Mock(return_value=parsed)),
        patch(f"{MODULE}.verify", Mock(return_value=installed)),
        patch(f"{MODULE}.snapshot", Mock(return_value=dict.fromkeys(POLICY, False))),
        patch(f"{MODULE}.os") as os_,
        patch(f"{MODULE}.atomic_write") as write,
        pytest.raises(error),
    ):
        service.install_legacy("blob")

    os_.unlink.assert_not_called()
    write.assert_not_called()

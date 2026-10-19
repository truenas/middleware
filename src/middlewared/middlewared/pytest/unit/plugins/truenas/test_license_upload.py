from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from truenas_pylicensed import LicenseError

from middlewared.plugins.truenas.license import TrueNASLicenseService
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service_exception import ValidationError
from middlewared.utils.entitlements import POLICY

MODULE = "middlewared.plugins.truenas.license"
USER = SimpleNamespace(authenticated_credentials=Mock())


def status(issued_at):
    return SimpleNamespace(
        code=LicenseError.OK,
        valid=True,
        test=False,
        id="7c1e4b0a",
        issued_at=issued_at,
        type=None,
        error=None,
        has_feature=lambda name: False,
    )


@pytest.fixture(autouse=True)
def pending_file(tmp_path):
    with patch(f"{MODULE}.PROPAGATION_PENDING_FILE", str(tmp_path / "license_propagation_pending")):
        yield


def upload(app, delivered, installed):
    middleware = Middleware()
    middleware["failover.status"] = Mock(return_value="MASTER")
    middleware["failover.in_progress"] = Mock(return_value=False)
    middleware["interface.query"] = Mock(return_value=[])
    service = create_service(middleware, TrueNASLicenseService)

    @contextmanager
    def upload_license(pem):
        yield delivered

    with (
        patch(f"{MODULE}.verify", Mock(return_value=installed)),
        patch(f"{MODULE}.get_license", Mock(return_value=None)),
        patch(f"{MODULE}.snapshot", Mock(return_value=dict.fromkeys(POLICY, False))),
        patch(f"{MODULE}.upload_license", upload_license),
    ):
        service.upload(app, "-----BEGIN LICENSE-----")


@pytest.mark.parametrize("app,refused", [(None, True), (USER, False)], ids=["tnc", "user"])
def test_older_license_refused_only_for_unattended_callers(app, refused):
    """A stale standby or TNC re-sending an old PEM must not undo a newer license; a user may downgrade."""
    older, newer = status("2026-01-01T00:00:00+00:00"), status("2026-06-01T00:00:00Z")
    if refused:
        with pytest.raises(ValidationError, match="older"):
            upload(app, older, newer)
    else:
        upload(app, older, newer)

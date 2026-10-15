from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from middlewared.plugins import failover
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware

OLD_V2 = {"id": "v2-old", "issued_at": "2026-01-01T00:00:00Z"}
NEW_V2 = {"id": "v2-new", "issued_at": "2026-06-01T00:00:00Z"}
SYSTEM_GENERATED = {"id": "system", "issued_at": None}
INVALID = SimpleNamespace(valid=False, test=False, issued_at=None)


def valid(license_, test=False):
    return SimpleNamespace(valid=True, test=test, issued_at=license_["issued_at"])


def push(monkeypatch, local, remote):
    monkeypatch.setattr(failover, "verify", lambda: local)
    uploads = []

    def call_remote(method, args=None):
        if method == "truenas.license.upload":
            uploads.append(args)
        else:
            return remote

    m = Middleware()
    m["truenas.license.propagate_pending"] = lambda: False
    m["truenas.license.installed_pem"] = lambda: "PEM"
    m["failover.call_remote"] = call_remote
    m["alert.alert_source_clear_run"] = Mock()
    create_service(m, failover.FailoverService).push_license_if_newer()
    return uploads, m["alert.alert_source_clear_run"]


@pytest.mark.parametrize(
    "local, remote",
    [
        (INVALID, NEW_V2),
        (valid(NEW_V2), None),
        (valid(NEW_V2), SYSTEM_GENERATED),
        (valid(NEW_V2, test=True), OLD_V2),
        (valid(OLD_V2), NEW_V2),
        (valid(NEW_V2), NEW_V2),
    ],
)
def test_no_push_that_could_replace_a_newer_or_production_license(monkeypatch, caplog, local, remote):
    uploads, clear = push(monkeypatch, local, remote)

    assert uploads == []
    assert "failed to push" not in caplog.text
    clear.assert_not_called()


def test_newer_v2_license_reaches_a_stale_peer(monkeypatch):
    uploads, clear = push(monkeypatch, valid(NEW_V2), OLD_V2)

    assert uploads == [["PEM", {"ha_propagate": False}]]
    clear.assert_called_once_with("LicenseStatus")

"""
Unit tests for expiry of the directory services user and group cache when the Active Directory
idmap configuration changes through directoryservices.update.

The cache holds the UIDs and GIDs assigned under the idmap configuration in effect when it was
built. Configuration changes are only permitted while directory services are disabled, so an
idmap change is usually saved in the call that disables them or in a later call while they are
disabled. The stored configuration then already matches when they are re-enabled, so the change
must be detected and the cache expired when it is saved.
"""

import logging
from unittest.mock import MagicMock, patch

from middlewared.plugins.directoryservices_.datastore import DirectoryServices
from middlewared.utils.directoryservices.constants import DSCredType, DSType
import pytest

BUILTIN_IDMAP = {"range_low": 90000001, "range_high": 100000000}

RID_IDMAP = {
    "builtin": BUILTIN_IDMAP,
    "idmap_domain": {
        "name": "AD04",
        "idmap_backend": "RID",
        "range_low": 100000001,
        "range_high": 200000000,
    },
}

AD_IDMAP = {
    "builtin": BUILTIN_IDMAP,
    "idmap_domain": {
        "name": "AD04",
        "idmap_backend": "AD",
        "range_low": 10000,
        "range_high": 90000000,
        "schema_mode": "RFC2307",
        "unix_primary_group": False,
    },
}

TRUSTED_DOMAIN = {
    "name": "CANARY",
    "idmap_backend": "RID",
    "range_low": 200000001,
    "range_high": 300000000,
}


def ad_config(**changes):
    return {
        "hostname": "truenas",
        "domain": "ad04.local",
        "idmap": RID_IDMAP,
        "site": None,
        "computer_account_ou": None,
        "use_default_domain": False,
        "enable_trusted_domains": False,
        "trusted_domains": [],
    } | changes


def ds_config(**changes):
    """Directory services configuration as returned by directoryservices.config"""
    return {
        "id": 1,
        "service_type": DSType.AD.value,
        "enable": True,
        "enable_account_cache": True,
        "enable_dns_updates": True,
        "timeout": 10,
        "kerberos_realm": None,
        "credential": {
            "credential_type": DSCredType.KERBEROS_PRINCIPAL,
            "principal": "TRUENAS$@AD04.LOCAL",
        },
        "configuration": ad_config(),
    } | changes


@pytest.fixture
def ds_service():
    svc = object.__new__(DirectoryServices)
    svc.middleware = MagicMock()
    svc.logger = logging.getLogger("test_directoryservices_idmap_cache")
    return svc


def run_update(ds_service, old, data):
    """Run the body of directoryservices.update for a request that leaves directory services disabled.

    Returns the mock for expire_cache and the list of middleware.call_sync calls that were made.
    """

    def fake_call_sync(method, *args, **kwargs):
        match method:
            case "directoryservices.config":
                return old
            case "failover.is_single_master_node":
                return True
            case (
                "datastore.update"
                | "directoryservices.health.set_state"
                | "etc.generate"
                | "directoryservices.restart_dependent_services"
            ):
                return None

        raise AssertionError(f"unexpected middleware call_sync: {method}")

    ds_service.middleware.call_sync = MagicMock(side_effect=fake_call_sync)

    with patch("middlewared.plugins.directoryservices_.datastore.expire_cache") as expire_mock:
        # bypass the api_method argument validation wrapper
        DirectoryServices.update.__wrapped__(ds_service, MagicMock(), data)

    return expire_mock, ds_service.middleware.call_sync.call_args_list


@pytest.mark.parametrize(
    "old, new, expected",
    [
        pytest.param(ds_config(), ds_config(configuration=ad_config(idmap=AD_IDMAP)), True, id="backend"),
        pytest.param(
            ds_config(),
            ds_config(
                configuration=ad_config(
                    idmap=RID_IDMAP
                    | {
                        "idmap_domain": RID_IDMAP["idmap_domain"] | {"range_high": 300000000},
                    }
                )
            ),
            True,
            id="range",
        ),
        pytest.param(
            ds_config(),
            ds_config(configuration=ad_config(enable_trusted_domains=True, trusted_domains=[TRUSTED_DOMAIN])),
            True,
            id="trusted_domains",
        ),
        pytest.param(ds_config(), ds_config(configuration=ad_config(site="NYC")), False, id="unrelated_change"),
        pytest.param(ds_config(), ds_config(enable=False), False, id="disable_only"),
        pytest.param(
            ds_config(service_type=DSType.IPA.value, configuration={"domain": "ipa.local"}),
            ds_config(service_type=DSType.IPA.value, configuration={"domain": "ipa2.local"}),
            False,
            id="not_ad",
        ),
        pytest.param(
            ds_config(enable=False, service_type=None, credential=None, configuration=None),
            ds_config(),
            False,
            id="no_previous_configuration",
        ),
    ],
)
def test__idmap_config_changed(ds_service, old, new, expected):
    assert ds_service.idmap_config_changed(old, new) is expected


def test__disable_with_idmap_change_expires_cache(ds_service):
    """
    Regression test: the idmap backend change was saved in the call that disabled directory services. The
    stored configuration then matched on re-enable, the cache was not expired and group.query kept returning
    GIDs from the old backend that no longer resolved.
    """
    expire_mock, calls = run_update(
        ds_service,
        ds_config(),
        {
            "enable": False,
            "configuration": ad_config(idmap=AD_IDMAP),
        },
    )

    assert expire_mock.call_count == 1

    updates = [c for c in calls if c.args[0] == "datastore.update"]
    assert len(updates) == 1
    assert updates[0].args[1:3] == ("directoryservices", 1)
    assert updates[0].args[3]["ad_idmap"] == AD_IDMAP


def test__idmap_change_while_disabled_expires_cache(ds_service):
    expire_mock, _ = run_update(
        ds_service,
        ds_config(enable=False),
        {
            "enable": False,
            "configuration": ad_config(idmap=AD_IDMAP),
        },
    )

    assert expire_mock.call_count == 1


def test__disable_without_idmap_change_keeps_cache(ds_service):
    """Disabling alone must not force a rebuild on the next enable."""
    expire_mock, _ = run_update(ds_service, ds_config(), {"enable": False})

    assert expire_mock.call_count == 0

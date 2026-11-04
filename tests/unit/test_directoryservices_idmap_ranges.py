"""Unit tests for the overlap check on Active Directory idmap ranges in directoryservices.update."""

from unittest.mock import MagicMock

from middlewared.plugins.directoryservices_.datastore import DirectoryServices
from middlewared.service_exception import ValidationErrors
from middlewared.utils.directoryservices.constants import DSCredType, DSType
import pytest

ATTR = "directoryservices.update.configuration"
BUILTIN = {"name": None, "range_low": 90000001, "range_high": 100000000}
PRIMARY = {"name": "AD03", "idmap_backend": "RID", "range_low": 100000001, "range_high": 200000000}
AD_PRIMARY = PRIMARY | {"idmap_backend": "AD"}
NOT_CONFIGURED = {"service_type": None, "enable": False, "configuration": None}


def trusted(range_low, range_high, idmap_backend="RID", name="DOMAIN1"):
    return {"name": name, "idmap_backend": idmap_backend, "range_low": range_low, "range_high": range_high}


OVERLAP = trusted(150000001, 300000000)


def ds_config(*trusted_domains, enable=True, enable_trusted_domains=True, idmap_domain=PRIMARY):
    return {
        "id": 1,
        "service_type": DSType.AD.value,
        "enable": enable,
        "kerberos_realm": None,
        "credential": {"credential_type": DSCredType.KERBEROS_PRINCIPAL, "principal": "TRUENAS$@AD03.LOCAL"},
        "configuration": {
            "idmap": {"builtin": BUILTIN, "idmap_domain": idmap_domain},
            "enable_trusted_domains": enable_trusted_domains,
            "trusted_domains": list(trusted_domains),
        },
    }


def without_builtin(config):
    idmap = {"idmap_domain": config["configuration"]["idmap"]["idmap_domain"]}
    return config | {"configuration": config["configuration"] | {"idmap": idmap}}


@pytest.fixture
def ds_service():
    svc = object.__new__(DirectoryServices)
    svc.middleware = MagicMock()
    return svc


def errors(ds_service, old, new):
    verrors = ValidationErrors()
    ds_service.validate_idmap_ranges(old, new, verrors)
    return [(attribute, errmsg) for attribute, errmsg, _ in verrors]


@pytest.mark.parametrize(
    "new, attributes",
    [
        pytest.param(ds_config(OVERLAP), ["trusted_domains.0"], id="trusted_overlaps_primary"),
        pytest.param(ds_config(trusted(95000000, 99000000)), ["trusted_domains.0"], id="trusted_overlaps_builtin"),
        pytest.param(ds_config(trusted(200000000, 300000000)), ["trusted_domains.0"], id="ranges_share_one_id"),
        pytest.param(
            ds_config(trusted(50000000, 300000000)),
            ["trusted_domains.0", "trusted_domains.0"],
            id="trusted_spans_builtin_and_primary",
        ),
        pytest.param(
            ds_config(idmap_domain=PRIMARY | {"range_low": 95000000}),
            ["idmap.idmap_domain"],
            id="primary_overlaps_builtin",
        ),
        pytest.param(
            ds_config(OVERLAP, idmap_domain=AD_PRIMARY),
            ["trusted_domains.0"],
            id="ad_backend_overlaps_other_backend",
        ),
        pytest.param(
            ds_config(idmap_domain=AD_PRIMARY | {"range_low": 95000000}),
            ["idmap.idmap_domain"],
            id="ad_backend_overlaps_builtin",
        ),
    ],
)
def test__overlap_is_rejected(ds_service, new, attributes):
    result = errors(ds_service, NOT_CONFIGURED, new)
    assert [attribute for attribute, _ in result] == [f"{ATTR}.{attribute}" for attribute in attributes]


@pytest.mark.parametrize(
    "new, errmsg",
    [
        pytest.param(
            ds_config(OVERLAP),
            "Idmap range [150000001-300000000] for DOMAIN1 conflicts with range [100000001-200000000] for AD03.",
            id="primary",
        ),
        pytest.param(
            ds_config(trusted(95000000, 99000000)),
            "Idmap range [95000000-99000000] for DOMAIN1 conflicts with range [90000001-100000000] for BUILTIN.",
            id="builtin",
        ),
        pytest.param(
            ds_config(OVERLAP, idmap_domain=PRIMARY | {"name": None}),
            "Idmap range [150000001-300000000] for DOMAIN1 conflicts with range [100000001-200000000] for "
            "the primary domain.",
            id="primary_without_name",
        ),
    ],
)
def test__error_message(ds_service, new, errmsg):
    assert [message for _, message in errors(ds_service, NOT_CONFIGURED, new)] == [errmsg]


@pytest.mark.parametrize(
    "new",
    [
        pytest.param(ds_config(trusted(200000001, 300000000)), id="adjacent_ranges"),
        pytest.param(
            ds_config(trusted(100000001, 200000000, "AD"), idmap_domain=AD_PRIMARY),
            id="both_domains_use_ad_backend",
        ),
        pytest.param(ds_config(OVERLAP, enable_trusted_domains=False), id="trusted_domains_disabled"),
    ],
)
def test__no_conflict(ds_service, new):
    assert errors(ds_service, NOT_CONFIGURED, new) == []


@pytest.mark.parametrize(
    "old, new",
    [
        pytest.param(ds_config(OVERLAP), ds_config(OVERLAP, enable=False), id="disable"),
        pytest.param(ds_config(OVERLAP, enable=False), ds_config(OVERLAP), id="enable"),
        pytest.param(ds_config(OVERLAP), ds_config(OVERLAP), id="update_while_enabled"),
        pytest.param(
            ds_config(OVERLAP),
            ds_config(OVERLAP, trusted(300000001, 400000000, name="DOMAIN2")),
            id="add_unrelated_trusted_domain",
        ),
        pytest.param(ds_config(OVERLAP | {"sssd_compat": False}), ds_config(OVERLAP), id="saved_row_has_other_keys"),
        pytest.param(
            ds_config(OVERLAP, idmap_domain={k: v for k, v in PRIMARY.items() if k != "name"}),
            ds_config(OVERLAP),
            id="saved_primary_has_no_name",
        ),
        pytest.param(without_builtin(ds_config(OVERLAP)), without_builtin(ds_config(OVERLAP)), id="saved_no_builtin"),
        pytest.param(ds_config(OVERLAP), ds_config(trusted(200000001, 300000000)), id="overlap_is_fixed"),
    ],
)
def test__existing_setup_keeps_working(ds_service, old, new):
    assert errors(ds_service, old, new) == []


@pytest.mark.parametrize(
    "old, new",
    [
        pytest.param(ds_config(enable=False), ds_config(OVERLAP, enable=False), id="saved_while_disabled"),
        pytest.param(ds_config(), ds_config(OVERLAP, enable=False), id="saved_in_disabling_call"),
        pytest.param(ds_config(enable=False), ds_config(OVERLAP), id="saved_in_enabling_call"),
        pytest.param(
            {"service_type": DSType.LDAP.value, "enable": False, "configuration": {"basedn": "dc=ad03"}},
            ds_config(OVERLAP),
            id="switch_from_other_service",
        ),
        pytest.param(ds_config(OVERLAP), ds_config(trusted(140000001, 300000000)), id="range_changed"),
        pytest.param(
            ds_config(trusted(150000001, 300000000, "AD"), idmap_domain=AD_PRIMARY),
            ds_config(OVERLAP, idmap_domain=AD_PRIMARY),
            id="ad_backend_replaced",
        ),
        pytest.param(
            ds_config(OVERLAP, enable_trusted_domains=False),
            ds_config(OVERLAP),
            id="trusted_domains_enabled",
        ),
        pytest.param(
            ds_config(OVERLAP),
            ds_config(OVERLAP, trusted(160000001, 170000000, name="DOMAIN2")),
            id="another_domain_overlaps",
        ),
    ],
)
def test__update_introducing_overlap_is_rejected(ds_service, old, new):
    assert errors(ds_service, old, new)


def test__other_service_type_is_not_checked(ds_service):
    new = {"service_type": DSType.IPA.value, "enable": True, "configuration": {"domain": "ipa.local"}}
    assert errors(ds_service, NOT_CONFIGURED, new) == []


def test__update_rejects_overlap_before_saving(ds_service):
    def call_sync(method, *args, **kwargs):
        match method:
            case "directoryservices.config":
                return ds_config()
            case "failover.is_single_master_node":
                return True

        raise AssertionError(f"unexpected middleware call_sync: {method}")

    ds_service.middleware.call_sync = MagicMock(side_effect=call_sync)

    with pytest.raises(ValidationErrors):
        # bypass the api_method argument validation wrapper
        DirectoryServices.update.__wrapped__(
            ds_service,
            MagicMock(),
            {"enable": False, "configuration": ds_config(OVERLAP)["configuration"]},
        )

"""Unit tests for the checks on Active Directory idmap ranges and domain names in directoryservices.update."""

from unittest.mock import MagicMock, call, patch

import pytest

from middlewared.plugins.directoryservices_.datastore import DirectoryServices
from middlewared.service_exception import ValidationErrors
from middlewared.utils.directoryservices.constants import DSCredType, DSType

ATTR = "directoryservices.update.configuration"
CREDENTIAL = "middlewared.utils.directoryservices.credential"
PRINCIPAL = "TRUENAS$@AD03.LOCAL"
BUILTIN = {"name": None, "range_low": 90000001, "range_high": 100000000}
PRIMARY = {"name": "AD03", "idmap_backend": "RID", "range_low": 100000001, "range_high": 200000000}
AD_PRIMARY = PRIMARY | {"idmap_backend": "AD"}
NOT_CONFIGURED = {"service_type": None, "enable": False, "configuration": None}


def trusted(range_low, range_high, idmap_backend="RID", name="DOMAIN1"):
    return {"name": name, "idmap_backend": idmap_backend, "range_low": range_low, "range_high": range_high}


OVERLAP = trusted(150000001, 300000000)
AD_OVERLAP = trusted(150000001, 300000000, "AD")
PRIMARY_COPY = trusted(100000001, 200000000)
UNRELATED = trusted(300000001, 400000000, name="DOMAIN2")
USES_PRIMARY_NAME = trusted(300000001, 400000000, name="AD03")
DOMAIN1 = trusted(200000001, 300000000)
DOMAIN1_AGAIN = trusted(300000001, 400000000)


def ds_config(*trusted_domains, enable=True, enable_trusted_domains=True, idmap_domain=PRIMARY, builtin=BUILTIN):
    return {
        "id": 1,
        "service_type": DSType.AD.value,
        "enable": enable,
        "kerberos_realm": None,
        "credential": {"credential_type": DSCredType.KERBEROS_PRINCIPAL, "principal": PRINCIPAL},
        "configuration": {
            "domain": "ad03.local",
            "idmap": {"builtin": builtin, "idmap_domain": idmap_domain},
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


def collect(validate, old, new):
    verrors = ValidationErrors()
    validate(old, new, verrors)
    return [(attribute, errmsg) for attribute, errmsg, _ in verrors]


def errors(ds_service, old, new):
    return collect(ds_service.validate_idmap_ranges, old, new)


def name_errors(ds_service, old, new):
    return collect(ds_service.validate_idmap_names, old, new)


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
        pytest.param(
            ds_config(AD_OVERLAP, idmap_domain=AD_PRIMARY),
            ["trusted_domains.0"],
            id="both_domains_use_ad_backend",
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
            ds_config(OVERLAP, UNRELATED),
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
        pytest.param(
            ds_config(AD_OVERLAP, idmap_domain=AD_PRIMARY),
            ds_config(AD_OVERLAP, idmap_domain=AD_PRIMARY),
            id="saved_ad_backend_overlap",
        ),
        pytest.param(ds_config(PRIMARY_COPY), ds_config(PRIMARY_COPY), id="saved_copy_of_primary"),
        pytest.param(ds_config(OVERLAP, UNRELATED), ds_config(UNRELATED, OVERLAP), id="trusted_domains_reordered"),
        pytest.param(ds_config(UNRELATED, OVERLAP), ds_config(OVERLAP), id="earlier_trusted_domain_removed"),
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
            ds_config(AD_OVERLAP, idmap_domain=AD_PRIMARY),
            ds_config(OVERLAP, idmap_domain=AD_PRIMARY),
            id="ad_backend_replaced",
        ),
        pytest.param(
            ds_config(AD_OVERLAP, idmap_domain=AD_PRIMARY),
            ds_config(trusted(140000001, 300000000, "AD"), idmap_domain=AD_PRIMARY),
            id="ad_backend_range_changed",
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
        pytest.param(ds_config(), ds_config(PRIMARY_COPY), id="trusted_copies_primary"),
        pytest.param(ds_config(), ds_config(PRIMARY_COPY | {"name": "AD03"}), id="trusted_copies_primary_and_its_name"),
        pytest.param(
            ds_config(idmap_domain=AD_PRIMARY),
            ds_config(PRIMARY_COPY | {"idmap_backend": "AD"}, idmap_domain=AD_PRIMARY),
            id="trusted_copies_ad_backend_primary",
        ),
        pytest.param(
            ds_config(PRIMARY_COPY, enable_trusted_domains=False),
            ds_config(PRIMARY_COPY),
            id="copy_of_primary_enabled",
        ),
        pytest.param(
            ds_config(UNRELATED),
            ds_config(UNRELATED, idmap_domain=PRIMARY | {"range_low": 300000001, "range_high": 400000000}),
            id="primary_copies_trusted",
        ),
        pytest.param(
            ds_config(OVERLAP, UNRELATED),
            ds_config(UNRELATED | {"name": "DOMAIN1"}, OVERLAP | {"name": "DOMAIN2"}),
            id="trusted_domains_swap_ranges",
        ),
        pytest.param(ds_config(OVERLAP), ds_config(OVERLAP | {"name": "DOMAIN2"}), id="replacement_inherits_range"),
    ],
)
def test__update_introducing_overlap_is_rejected(ds_service, old, new):
    assert errors(ds_service, old, new)


def test__other_service_type_is_not_checked(ds_service):
    new = {"service_type": DSType.IPA.value, "enable": True, "configuration": {"domain": "ipa.local"}}
    assert errors(ds_service, NOT_CONFIGURED, new) == []


@pytest.mark.parametrize(
    "domain",
    [
        pytest.param(OVERLAP, id="range"),
        pytest.param(USES_PRIMARY_NAME, id="name"),
    ],
)
def test__update_rejects_conflict_before_saving(ds_service, domain):
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
            {"enable": False, "configuration": ds_config(domain)["configuration"]},
        )


@pytest.mark.parametrize(
    "new, attributes",
    [
        pytest.param(ds_config(USES_PRIMARY_NAME), ["trusted_domains.0"], id="trusted_uses_primary_name"),
        pytest.param(
            ds_config(USES_PRIMARY_NAME | {"name": "ad03"}),
            ["trusted_domains.0"],
            id="trusted_uses_primary_name_in_other_case",
        ),
        pytest.param(ds_config(UNRELATED, USES_PRIMARY_NAME), ["trusted_domains.1"], id="later_trusted_domain"),
        pytest.param(ds_config(DOMAIN1, DOMAIN1_AGAIN), ["trusted_domains.1"], id="trusted_domains_share_name"),
        pytest.param(
            ds_config(DOMAIN1, DOMAIN1_AGAIN | {"name": "domain1"}),
            ["trusted_domains.1"],
            id="trusted_domains_differ_by_case",
        ),
        pytest.param(
            ds_config(USES_PRIMARY_NAME, enable_trusted_domains=False),
            ["trusted_domains.0"],
            id="trusted_domains_disabled",
        ),
        pytest.param(
            ds_config(DOMAIN1, DOMAIN1_AGAIN, enable_trusted_domains=False),
            ["trusted_domains.1"],
            id="duplicates_while_trusted_domains_disabled",
        ),
        pytest.param(
            ds_config(DOMAIN1 | {"name": "AD03"}, USES_PRIMARY_NAME),
            ["trusted_domains.0", "trusted_domains.1", "trusted_domains.1"],
            id="primary_and_two_trusted_domains",
        ),
    ],
)
def test__duplicate_name_is_rejected(ds_service, new, attributes):
    result = name_errors(ds_service, NOT_CONFIGURED, new)
    assert [attribute for attribute, _ in result] == [f"{ATTR}.{attribute}" for attribute in attributes]


@pytest.mark.parametrize(
    "new, errmsg",
    [
        pytest.param(
            ds_config(USES_PRIMARY_NAME), "Domain name AD03 is already used by the primary domain.", id="primary"
        ),
        pytest.param(
            ds_config(DOMAIN1, DOMAIN1_AGAIN | {"name": "domain1"}),
            "Domain name domain1 is already used by trusted domain DOMAIN1.",
            id="trusted",
        ),
    ],
)
def test__duplicate_name_error_message(ds_service, new, errmsg):
    assert [message for _, message in name_errors(ds_service, NOT_CONFIGURED, new)] == [errmsg]


@pytest.mark.parametrize(
    "new",
    [
        pytest.param(ds_config(DOMAIN1, UNRELATED), id="unique_names"),
        pytest.param(ds_config(USES_PRIMARY_NAME, idmap_domain=PRIMARY | {"name": None}), id="primary_without_name"),
        pytest.param(
            ds_config(DOMAIN1, builtin=BUILTIN | {"name": "DOMAIN1"}),
            id="name_of_builtin_is_not_used",
        ),
        pytest.param(
            {"service_type": DSType.IPA.value, "enable": True, "configuration": {"domain": "ipa.local"}},
            id="other_service_type",
        ),
    ],
)
def test__no_name_conflict(ds_service, new):
    assert name_errors(ds_service, NOT_CONFIGURED, new) == []


@pytest.mark.parametrize(
    "old, new",
    [
        pytest.param(ds_config(USES_PRIMARY_NAME), ds_config(USES_PRIMARY_NAME, enable=False), id="disable"),
        pytest.param(ds_config(USES_PRIMARY_NAME, enable=False), ds_config(USES_PRIMARY_NAME), id="enable"),
        pytest.param(ds_config(USES_PRIMARY_NAME), ds_config(USES_PRIMARY_NAME), id="update_while_enabled"),
        pytest.param(ds_config(DOMAIN1, DOMAIN1_AGAIN), ds_config(DOMAIN1, DOMAIN1_AGAIN), id="saved_duplicates"),
        pytest.param(
            ds_config(DOMAIN1, DOMAIN1_AGAIN),
            ds_config(DOMAIN1_AGAIN, DOMAIN1),
            id="saved_duplicates_reordered",
        ),
        pytest.param(
            ds_config(USES_PRIMARY_NAME | {"sssd_compat": False}),
            ds_config(USES_PRIMARY_NAME),
            id="saved_row_has_other_keys",
        ),
        pytest.param(
            ds_config(USES_PRIMARY_NAME, enable_trusted_domains=False),
            ds_config(USES_PRIMARY_NAME, enable_trusted_domains=False),
            id="saved_while_trusted_domains_disabled",
        ),
        pytest.param(
            ds_config(USES_PRIMARY_NAME, enable_trusted_domains=False),
            ds_config(USES_PRIMARY_NAME),
            id="trusted_domains_enabled",
        ),
        pytest.param(
            ds_config(USES_PRIMARY_NAME),
            ds_config(USES_PRIMARY_NAME, trusted(400000001, 500000000, name="DOMAIN2")),
            id="add_unrelated_trusted_domain",
        ),
        pytest.param(
            ds_config(USES_PRIMARY_NAME),
            ds_config(USES_PRIMARY_NAME | {"name": "DOMAIN1"}),
            id="collision_is_fixed",
        ),
    ],
)
def test__existing_name_collision_keeps_working(ds_service, old, new):
    assert name_errors(ds_service, old, new) == []


@pytest.mark.parametrize(
    "old, new",
    [
        pytest.param(ds_config(enable=False), ds_config(USES_PRIMARY_NAME, enable=False), id="saved_while_disabled"),
        pytest.param(ds_config(), ds_config(USES_PRIMARY_NAME, enable=False), id="saved_in_disabling_call"),
        pytest.param(ds_config(enable=False), ds_config(USES_PRIMARY_NAME), id="saved_in_enabling_call"),
        pytest.param(
            {"service_type": DSType.LDAP.value, "enable": False, "configuration": {"basedn": "dc=ad03"}},
            ds_config(USES_PRIMARY_NAME),
            id="switch_from_other_service",
        ),
        pytest.param(ds_config(UNRELATED), ds_config(UNRELATED | {"name": "AD03"}), id="trusted_domain_renamed"),
        pytest.param(
            ds_config(UNRELATED),
            ds_config(UNRELATED, idmap_domain=PRIMARY | {"name": "DOMAIN2"}),
            id="primary_domain_renamed",
        ),
        pytest.param(
            ds_config(UNRELATED, idmap_domain=PRIMARY | {"name": None}),
            ds_config(UNRELATED, idmap_domain=PRIMARY | {"name": "DOMAIN2"}),
            id="primary_domain_gets_name",
        ),
        pytest.param(
            ds_config(enable_trusted_domains=False),
            ds_config(PRIMARY_COPY | {"name": "AD03"}, enable_trusted_domains=False),
            id="trusted_domain_copies_all_primary_settings",
        ),
        pytest.param(
            ds_config(USES_PRIMARY_NAME),
            ds_config(USES_PRIMARY_NAME, trusted(400000001, 500000000, name="ad03")),
            id="another_domain_joins_collision",
        ),
        pytest.param(
            ds_config(USES_PRIMARY_NAME),
            ds_config(USES_PRIMARY_NAME | {"range_high": 500000000}),
            id="range_of_collision_changed",
        ),
        pytest.param(
            ds_config(USES_PRIMARY_NAME),
            ds_config(USES_PRIMARY_NAME | {"idmap_backend": "AD"}),
            id="backend_of_collision_changed",
        ),
    ],
)
def test__update_introducing_name_collision_is_rejected(ds_service, old, new):
    assert name_errors(ds_service, old, new)


class ReachedDnsValidation(Exception):
    pass


def enable_with_workgroup(ds_service, saved, data, workgroup):
    """Run the body of directoryservices.update for a request that enables directory services, stopping at the DNS
    checks that follow credential validation. Credential validation is the real code, with only its calls to the
    domain controller and the system replaced. It stores the workgroup that the domain controller reports as the name
    of the primary domain."""

    def fake_call_sync(method, *args, **kwargs):
        match method:
            case "directoryservices.config":
                return saved
            case "failover.is_single_master_node":
                return True
            case "idmap.clear_idmap_cache" | "kerberos.kdestroy" | "etc.generate":
                return MagicMock()

        raise AssertionError(f"unexpected middleware call_sync: {method}")

    ds_service.middleware.call_sync = MagicMock(side_effect=fake_call_sync)
    ds_service.validate_dns = MagicMock(side_effect=ReachedDnsValidation)
    domain_info = {"workgroup": workgroup, "server_time_offset": 0, "kdc_server": "192.0.2.1"}

    with (
        patch("middlewared.plugins.directoryservices_.datastore.expire_cache"),
        patch(f"{CREDENTIAL}.get_domain_info", return_value=domain_info),
        patch(f"{CREDENTIAL}.lookup_dc", return_value={"domain_controller": "dc.ad03.local"}),
        patch(f"{CREDENTIAL}.kdc_saf_cache_set"),
        patch(f"{CREDENTIAL}.KRB5Conf"),
        patch(f"{CREDENTIAL}.ktutil_list_impl", return_value=[{"principal": PRINCIPAL}]),
        patch(f"{CREDENTIAL}.kinit_with_cred"),
    ):
        # bypass the api_method argument validation wrapper
        DirectoryServices.update.__wrapped__(ds_service, MagicMock(), data)


def unnamed_primary(*trusted_domains):
    """A new copy of a disabled configuration whose primary domain does not have a name yet."""
    return ds_config(*trusted_domains, enable=False, idmap_domain=PRIMARY | {"name": None})


@pytest.mark.parametrize("send_configuration", [False, True], ids=["configuration_saved_earlier", "configuration_sent"])
def test__update_rejects_collision_with_name_from_domain_controller(ds_service, send_configuration):
    data = {"enable": True}
    if send_configuration:
        data["configuration"] = unnamed_primary(USES_PRIMARY_NAME)["configuration"]

    with pytest.raises(ValidationErrors) as exc:
        enable_with_workgroup(ds_service, unnamed_primary(USES_PRIMARY_NAME), data, "AD03")

    assert [attribute for attribute, _, _ in exc.value] == [f"{ATTR}.trusted_domains.0"]
    ds_service.validate_dns.assert_not_called()
    assert call("etc.generate", "kerberos") in ds_service.middleware.call_sync.call_args_list


@pytest.mark.parametrize(
    "saved",
    [
        pytest.param(ds_config(USES_PRIMARY_NAME, enable=False), id="saved_collision"),
        pytest.param(unnamed_primary(UNRELATED), id="no_collision"),
    ],
)
def test__update_continues_after_name_from_domain_controller(ds_service, saved):
    with pytest.raises(ReachedDnsValidation):
        enable_with_workgroup(ds_service, saved, {"enable": True}, "AD03")


def test__credential_validation_updates_new_and_leaves_saved_configuration_alone(ds_service):
    saved = unnamed_primary(UNRELATED)

    with pytest.raises(ReachedDnsValidation):
        enable_with_workgroup(ds_service, saved, {"enable": True}, "AD03")

    new = ds_service.validate_dns.call_args.args[1]
    assert new["configuration"]["domain"] == "AD03.LOCAL"
    assert new["configuration"]["idmap"]["idmap_domain"]["name"] == "AD03"
    assert new["kerberos_realm"] == "AD03.LOCAL"
    # The update compares against the saved configuration and restores it if a later step fails.
    assert saved == unnamed_primary(UNRELATED)

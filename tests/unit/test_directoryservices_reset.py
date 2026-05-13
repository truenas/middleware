"""
Unit tests for directoryservices.reset() local-state cleanup. The fix
ensures that when reset() is called and the prior service_type was AD or
IPA, the AD/IPA-specific entries in secrets.tdb (or CTDB), the cifs.secrets
DB backup, the kerberos realm/keytab DB rows, and /etc/krb5.keytab are all
cleared. Without this, re-enabling silently reuses stale state via
_test_is_joined / ALREADY_JOINED.

The secrets cleanup is surgical (mimics samba's secrets_delete_machine_password_ex
on `net ads leave`): it removes machine-account / domain SID / domain GUID /
DES salt entries while preserving local-only keys (SAM/SID,
SECRETS/SID/{netbios}, SECRETS/GUID, SECRETS/LOCAL_SCHANNEL_KEY).
"""

import asyncio
import logging

import pytest

from unittest.mock import AsyncMock, MagicMock, patch

from middlewared.plugins.directoryservices_.datastore import DirectoryServices
from middlewared.utils.directoryservices.ad_constants import MACHINE_ACCOUNT_KT_NAME
from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.directoryservices.ipa_constants import IpaConfigName


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def ds_service():
    svc = object.__new__(DirectoryServices)
    svc.middleware = MagicMock()
    svc.middleware.call = AsyncMock()
    svc.middleware.run_in_thread = AsyncMock()
    svc.logger = logging.getLogger("test_directoryservices_reset")
    return svc


def test__reset_local_domain_state_ad_clears_all_local_state(ds_service):
    """
    When the prior service_type was AD, reset_local_domain_state must:
      * call delete_machine_account_secrets(workgroup, realm, cluster=False)
      * clear cifs.secrets in the DB (set to NULL)
      * delete the AD_MACHINE_ACCOUNT keytab DB row
      * delete the realm DB row identified by the captured FK id
      * unlink /etc/krb5.keytab

    The method is sync; middleware.call() runs it in the io thread pool. Tests
    drive call_sync directly here.
    """
    keytab_query_results = [{"id": 7, "name": MACHINE_ACCOUNT_KT_NAME}]

    def fake_call_sync(method, *args, **kwargs):
        if method == "datastore.update":
            return None
        if method == "kerberos.keytab.query":
            return keytab_query_results
        if method == "kerberos.realm.query":
            return [{"id": 42, "realm": "AD.EXAMPLE.COM"}]
        if method == "datastore.delete":
            return 1
        if method == "smb.config":
            return {"workgroup": "EXAMPLE", "stateful_failover": False}
        raise AssertionError(f"unexpected middleware call_sync: {method}")

    ds_service.middleware.call_sync = MagicMock(side_effect=fake_call_sync)
    with (
        patch(
            "middlewared.plugins.directoryservices_.datastore.os.unlink",
        ) as unlink_mock,
        patch(
            "middlewared.plugins.directoryservices_.datastore.delete_machine_account_secrets",
        ) as delete_secrets_mock,
    ):
        ds_service.reset_local_domain_state(DSType.AD.value, 42)

    # Surgical secrets cleanup called with the captured workgroup + realm; cluster=False.
    assert delete_secrets_mock.call_args_list == [
        (("EXAMPLE", "AD.EXAMPLE.COM", False), {})
    ]

    # cifs.secrets cleared
    cifs_update_calls = [
        c
        for c in ds_service.middleware.call_sync.call_args_list
        if c.args[:3] == ("datastore.update", "services.cifs", 1)
    ]
    assert len(cifs_update_calls) == 1
    assert cifs_update_calls[0].args[3] == {"secrets": None}

    # AD_MACHINE_ACCOUNT keytab row deleted
    keytab_delete_calls = [
        c
        for c in ds_service.middleware.call_sync.call_args_list
        if c.args[:2] == ("datastore.delete", "directoryservice.kerberoskeytab")
    ]
    assert len(keytab_delete_calls) == 1
    assert keytab_delete_calls[0].args[2] == 7

    # Realm row deleted (by the captured FK id, not the realm name)
    realm_delete_calls = [
        c
        for c in ds_service.middleware.call_sync.call_args_list
        if c.args[:2] == ("datastore.delete", "directoryservice.kerberosrealm")
    ]
    assert len(realm_delete_calls) == 1
    assert realm_delete_calls[0].args[2] == 42

    # /etc/krb5.keytab unlinked
    assert unlink_mock.call_count == 1


def test__reset_local_domain_state_ipa_uses_ipa_keytab_names(ds_service):
    """
    For IPA reset, the keytab cleanup queries the IPA-specific keytab names rather
    than AD_MACHINE_ACCOUNT.
    """
    queried_names = []

    def fake_call_sync(method, *args, **kwargs):
        if method == "datastore.update":
            return None
        if method == "kerberos.keytab.query":
            queried_names.append(args[0][0][2])  # filter is [['name', '=', kt_name]]
            return []
        if method == "kerberos.realm.query":
            return []
        if method == "smb.config":
            return {"workgroup": "EXAMPLE", "stateful_failover": False}
        return None

    ds_service.middleware.call_sync = MagicMock(side_effect=fake_call_sync)
    with (
        patch("middlewared.plugins.directoryservices_.datastore.os.unlink"),
        patch(
            "middlewared.plugins.directoryservices_.datastore.delete_machine_account_secrets"
        ),
    ):
        ds_service.reset_local_domain_state(DSType.IPA.value, None)

    assert set(queried_names) == {
        IpaConfigName.IPA_HOST_KEYTAB.value,
        IpaConfigName.IPA_SMB_KEYTAB.value,
        IpaConfigName.IPA_NFS_KEYTAB.value,
    }


def test__reset_local_domain_state_clustered_passes_cluster_flag(ds_service):
    """
    With stateful_failover the authoritative secrets store is in CTDB. The
    surgical delete helper must be invoked with cluster=True so it operates on
    the CTDB-backed store rather than the local file.
    """

    def fake_call_sync(method, *args, **kwargs):
        if method == "datastore.update":
            return None
        if method == "kerberos.keytab.query":
            return []
        if method == "kerberos.realm.query":
            return [{"id": 11, "realm": "AD.EXAMPLE.COM"}]
        if method == "smb.config":
            return {"workgroup": "EXAMPLE", "stateful_failover": True}
        return None

    ds_service.middleware.call_sync = MagicMock(side_effect=fake_call_sync)
    with (
        patch("middlewared.plugins.directoryservices_.datastore.os.unlink"),
        patch(
            "middlewared.plugins.directoryservices_.datastore.delete_machine_account_secrets"
        ) as delete_secrets_mock,
    ):
        ds_service.reset_local_domain_state(DSType.AD.value, 11)

    assert delete_secrets_mock.call_args_list == [
        (("EXAMPLE", "AD.EXAMPLE.COM", True), {})
    ], (
        "reset_local_domain_state must invoke delete_machine_account_secrets "
        "with cluster=True when stateful_failover is enabled."
    )


def test__reset_local_domain_state_no_realm_passes_none(ds_service):
    """
    If the prior config had no kerberos_realm_id (e.g. IPA bind that failed
    before realm setup, or a partially-cleaned state), realm should be passed
    as None so the secrets cleanup skips the SALTING_PRINCIPAL/DES key.
    """
    captured = []

    def fake_call_sync(method, *args, **kwargs):
        if method == "kerberos.keytab.query":
            return []
        if method == "smb.config":
            return {"workgroup": "EXAMPLE", "stateful_failover": False}
        return None

    ds_service.middleware.call_sync = MagicMock(side_effect=fake_call_sync)
    with (
        patch("middlewared.plugins.directoryservices_.datastore.os.unlink"),
        patch(
            "middlewared.plugins.directoryservices_.datastore.delete_machine_account_secrets",
            side_effect=lambda *a, **kw: captured.append(a),
        ),
    ):
        ds_service.reset_local_domain_state(DSType.AD.value, None)

    assert captured == [("EXAMPLE", None, False)]


def test__reset_local_domain_state_handles_missing_keytab_file(ds_service):
    """
    /etc/krb5.keytab may already be gone (e.g. after a prior leave or manual
    cleanup). FileNotFoundError must be swallowed so the rest of the cleanup
    still runs.
    """

    def fake_call_sync(method, *args, **kwargs):
        if method == "kerberos.keytab.query":
            return []
        if method == "kerberos.realm.query":
            return []
        if method == "smb.config":
            return {"workgroup": "EXAMPLE", "stateful_failover": False}
        return None

    ds_service.middleware.call_sync = MagicMock(side_effect=fake_call_sync)
    with (
        patch(
            "middlewared.plugins.directoryservices_.datastore.os.unlink",
            side_effect=FileNotFoundError,
        ),
        patch(
            "middlewared.plugins.directoryservices_.datastore.delete_machine_account_secrets"
        ),
    ):
        ds_service.reset_local_domain_state(DSType.AD.value, None)


def test__reset_does_not_clear_local_state_when_service_type_is_ldap(ds_service):
    """
    Reset triggered from a non-AD/non-IPA prior config must NOT route through the
    local-state cleanup -- LDAP binds don't have a samba secrets.tdb / keytab
    entanglement, and tearing down their unrelated local files would be wrong.
    """
    config_row = {
        "id": 1,
        "service_type": DSType.LDAP.value,
        "kerberos_realm_id": None,
        "enable": True,
        "timeout": 10,
        "cred_type": None,
        "cred_krb5": None,
    }

    routed_calls = []

    async def fake_call(method, *args, **kwargs):
        routed_calls.append((method, args))
        if method == "datastore.config":
            return dict(config_row)
        if method == "datastore.update":
            return None
        if method == "directoryservices.reset_local_domain_state":
            raise AssertionError(
                "reset_local_domain_state should not be invoked for non-AD/IPA prior"
            )
        return None

    ds_service.middleware.call.side_effect = fake_call

    with (
        patch("middlewared.plugins.directoryservices_.datastore.kdc_saf_cache_remove"),
        patch("middlewared.plugins.directoryservices_.datastore.expire_cache"),
    ):
        _run(ds_service.reset())

    assert not any(
        m == "directoryservices.reset_local_domain_state" for m, _ in routed_calls
    )


def test__reset_routes_through_middleware_call_for_ad(ds_service):
    """
    The AD path of reset() must dispatch reset_local_domain_state via
    middleware.call (which runs the sync implementation in the io thread pool)
    rather than awaiting it directly. This keeps the sync helper accessible to
    other callers and matches how reset() handles its other middleware ops.
    """
    config_row = {
        "id": 1,
        "service_type": DSType.AD.value,
        "kerberos_realm_id": 99,
        "enable": True,
        "timeout": 10,
        "cred_type": None,
        "cred_krb5": None,
    }

    routed = []

    async def fake_call(method, *args, **kwargs):
        routed.append((method, args))
        if method == "datastore.config":
            return dict(config_row)
        return None

    ds_service.middleware.call.side_effect = fake_call

    with (
        patch("middlewared.plugins.directoryservices_.datastore.kdc_saf_cache_remove"),
        patch("middlewared.plugins.directoryservices_.datastore.expire_cache"),
    ):
        _run(ds_service.reset())

    cleanup_routed = [
        (m, a) for m, a in routed if m == "directoryservices.reset_local_domain_state"
    ]
    assert len(cleanup_routed) == 1
    # Called with (old_service_type, old_kerberos_realm_id)
    assert cleanup_routed[0][1] == (DSType.AD.value, 99)

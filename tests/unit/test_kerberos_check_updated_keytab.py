"""
Unit tests for KerberosKeytabService.check_updated_keytab's decision to refresh the machine-account
keytab / secrets backup.

The skip guard must key on whether the machine account password is present (has_domain), NOT on
the last-password-change timestamp. Keying on the timestamp conflates two distinct states: the
startup window where secrets.tdb holds only the local server SID (password absent -- skip so we
don't clobber the good backup) and a corrupt/unreadable timestamp with the password intact
(which must not skip keytab refreshes forever).
"""

import asyncio
import logging

from unittest.mock import AsyncMock, MagicMock

from middlewared.plugins.kerberos import KerberosKeytabService


WORKGROUP = "AD"


def _kerberos_service(*, has_domain, last_change, capture_warnings=False):
    """
    Build a KerberosKeytabService whose middleware answers the calls check_updated_keytab makes.
    ``has_domain`` is the bool returned by directoryservices.secrets.has_domain; ``last_change``
    is the dict returned by directoryservices.get_last_password_change. Backup and keytab-store
    calls are recorded on svc.performed.
    """
    svc = object.__new__(KerberosKeytabService)
    svc.middleware = MagicMock()
    svc.middleware.call = AsyncMock()
    svc.logger = MagicMock() if capture_warnings else logging.getLogger("test_kerberos_keytab")
    svc.performed = []

    async def call(method, *args, **kwargs):
        match method:
            case "system.ready":
                return True
            case "failover.is_single_master_node":
                return True
            case "directoryservices.config":
                return {"enable": True, "service_type": "ACTIVEDIRECTORY"}
            case "smb.config":
                return {"workgroup": WORKGROUP}
            case "directoryservices.secrets.has_domain":
                assert args[0] == WORKGROUP
                return has_domain
            case "directoryservices.get_last_password_change":
                return last_change
            case "directoryservices.secrets.backup":
                svc.performed.append("backup")
                return None
            case "kerberos.keytab.store_ad_keytab":
                svc.performed.append("store_ad_keytab")
                return None
            case _:
                raise AssertionError(f"unexpected middleware call: {method}")

    svc.middleware.call.side_effect = call
    return svc


def _called(svc, method):
    return any(c.args[0] == method for c in svc.middleware.call.call_args_list)


def test_skips_when_machine_password_absent():
    """
    Startup window: secrets.tdb holds only the local server SID (no machine account password).
    has_domain is False -> skip before get_last_password_change, so nothing is backed up over
    the good DB backup.
    """
    svc = _kerberos_service(has_domain=False, last_change=None)

    asyncio.run(svc.check_updated_keytab())

    assert svc.performed == [], "no backup or keytab store when the machine password is absent"
    # get_last_password_change must not even be consulted once has_domain is False.
    assert not _called(svc, "directoryservices.get_last_password_change")


def test_skips_but_warns_when_timestamp_corrupt_with_password_present():
    """
    When the machine password is present but its last-change timestamp is unreadable
    (secrets=None from a corrupt entry), check_updated_keytab must skip WITHOUT backing up
    (don't propagate corruption over the good backup) and must log a warning rather than
    silently skipping keytab refreshes forever.
    """
    svc = _kerberos_service(
        has_domain=True,
        last_change={"dbconfig": 1718800000, "secrets": None},
        capture_warnings=True,
    )

    asyncio.run(svc.check_updated_keytab())

    assert svc.performed == [], "corrupt timestamp must not trigger a backup/keytab rewrite"
    assert svc.logger.warning.called, (
        "an unreadable timestamp with the password present must be logged, not silently skipped"
    )


def test_skips_when_timestamps_match():
    """Password present, timestamps equal -> nothing changed, no backup/keytab work."""
    svc = _kerberos_service(has_domain=True, last_change={"dbconfig": 1718800000, "secrets": 1718800000})

    asyncio.run(svc.check_updated_keytab())

    assert svc.performed == []


def test_backs_up_and_stores_keytab_on_password_change():
    """
    Password present and the secrets timestamp differs from the stored one -> a real rotation
    -> back up secrets and refresh the keytab.
    """
    svc = _kerberos_service(has_domain=True, last_change={"dbconfig": 1718800000, "secrets": 1718900000})

    asyncio.run(svc.check_updated_keytab())

    assert svc.performed == ["backup", "store_ad_keytab"]

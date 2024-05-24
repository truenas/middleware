#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
import json
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import hostname
from base64 import b64decode
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.directory_service import active_directory
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.system import reset_systemd_svcs

try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME, AD_COMPUTER_OU
    from config import (
        LDAPBASEDN,
        LDAPBINDDN,
        LDAPBINDPASSWORD,
        LDAPHOSTNAME
    )
except ImportError:
    Reason = 'ADNameServer AD_DOMAIN, ADPASSWORD, or/and ADUSERNAME are missing in config.py"'
    pytestmark = pytest.mark.skip(reason=Reason)

BACKENDS = [
    "AD",
    "AUTORID",
    "LDAP",
    "NSS",
    "RFC2307",
    "TDB",
    "RID",
]

@pytest.fixture(scope="function")
def idmap_domain():
    low, high = call('idmap.get_next_idmap_range')
    payload = {
        "name": "canary",
        "range_low": low,
        "range_high": high,
        "idmap_backend": "RID",
        "options": {},
    }
    new_idmap = call('idmap.create', payload)

    try:
        yield new_idmap
    finally:
        call('idmap.delete', new_idmap['id'])


@pytest.fixture(scope="module")
def do_ad_connection(request):
    call('service.update', 'cifs', {'enable': True})
    try:
        with active_directory(
            AD_DOMAIN,
            ADUSERNAME,
            ADPASSWORD,
            netbiosname=hostname,
            createcomputer=AD_COMPUTER_OU,
        ) as ad:
            yield ad
    finally:
        call('service.update', 'cifs', {'enable': False})


def assert_ad_healthy():
    ad_alerts = call('alert.run_source', 'ActiveDirectoryDomainBind')
    assert len(ad_alerts) == 0, str(ad_alerts)


@pytest.fixture(scope="module")
def backend_data():
    backend_options = call('idmap.backend_options')
    workgroup = call('smb.config')['workgroup']
    yield {'options': backend_options, 'workgroup': workgroup}


def test_name_sid_resolution(do_ad_connection):

    # get list of AD group gids for user from NSS
    ad_acct = call('user.get_user_obj', {'username': f'{ADUSERNAME}@{AD_DOMAIN}', 'get_groups': True})
    groups = set(ad_acct['grouplist'])

    # convert list of gids into sids
    sids = call('idmap.convert_unixids', [{'id_type': 'GROUP', 'id': x} for x in groups])
    sidlist = set([x['sid'] for x in sids['mapped'].values()])
    assert len(groups) == len(sidlist)

    # convert sids back into unixids
    unixids = call('idmap.convert_sids', list(sidlist))
    assert set([x['id'] for x in unixids['mapped'].values()]) == groups


@pytest.mark.parametrize('backend', BACKENDS)
def test_backend_options(do_ad_connection, backend_data, backend):
    """
    Tests for backend options are performend against
    the backend for the domain we're joined to
    (DS_TYPE_ACTIVEDIRECTORY) so that auto-detection
    works correctly. The three default idmap backends
    DS_TYPE_ACTIVEDIRECTORY, DS_TYPE_LDAP,
    DS_TYPE_DEFAULT_DOMAIN have hard-coded ids and
    so we don't need to look them up.
    """
    reset_systemd_svcs('winbind smbd')
    opts = backend_data['options'][backend]['parameters'].copy()
    WORKGROUP = backend_data['workgroup']
    set_secret = False

    payload = {
        "name": "DS_TYPE_ACTIVEDIRECTORY",
        "range_low": "1000000001",
        "range_high": "2000000000",
        "idmap_backend": backend,
        "options": {}
    }
    payload3 = {"options": {}}
    for k, v in opts.items():
        """
        Populate garbage data where an opt is required.
        This should get us past the first step of
        switching to the backend before doing more
        comprehensive tests.
        """
        if v['required']:
            payload["options"].update({k: "canary"})

    if backend == 'RFC2307':
        payload['options'].update({"ldap_server": "STANDALONE"})

    if not payload['options']:
        payload.pop('options')

    call('idmap.update', 1, payload)

    if backend == "AUTORID":
        IDMAP_CFG = "idmap config * "
    else:
        IDMAP_CFG = f"idmap config {WORKGROUP} "

    """
    Validate that backend was correctly set in smb.conf.
    """
    running_backend = call('smb.getparm', f'{IDMAP_CFG}: backend', 'GLOBAL')
    assert running_backend == backend.lower()

    if backend == "RID":
        """
        sssd_compat generates a lower range based
        on murmur3 hash of domain SID. Since we're validating
        basic functionilty, checking that our range_low
        changed is sufficient for now.
        """
        payload2 = {"options": {"sssd_compat": True}}
        out = call('idmap.update', 1, payload2)
        assert out['range_low'] != payload['range_low']

    elif backend == "AUTORID":
        """
        autorid is unique among the idmap backends because
        its configuration replaces the default idmap backend
        "idmap config *".
        """
        payload3["options"] = {
            "rangesize": 200000,
            "readonly": True,
            "ignore_builtin": True,
        }
        call('idmap.update', 1, payload3)

    elif backend == "AD":
        payload3["options"] = {
            "schema_mode": "SFU",
            "unix_primary_group": True,
            "unix_nss_info": True,
        }
        call('idmap.update', 1, payload3)

    elif backend == "LDAP":
        payload3["options"] = {
            "ldap_base_dn": LDAPBASEDN,
            "ldap_user_dn": LDAPBINDDN,
            "ldap_url": LDAPHOSTNAME,
            "ldap_user_dn_password": LDAPBINDPASSWORD,
            "ssl": "ON",
            "readonly": True,
        }
        call('idmap.update', 1, payload3)
        secret = payload3["options"].pop("ldap_user_dn_password")
        set_secret = True

    elif backend == "RFC2307":
        payload3["options"] = {
            "ldap_server": "STANDALONE",
            "bind_path_user": LDAPBASEDN,
            "bind_path_group": LDAPBASEDN,
            "user_cn": True,
            "ldap_domain": "",
            "ldap_url": LDAPHOSTNAME,
            "ldap_user_dn": LDAPBINDDN,
            "ldap_user_dn_password": LDAPBINDPASSWORD,
            "ssl": "ON",
            "ldap_realm": True,
        }
        call('idmap.update', 1, payload3)
        r = payload3["options"].pop("ldap_realm")
        payload3["options"]["realm"] = r
        secret = payload3["options"].pop("ldap_user_dn_password")
        set_secret = True

    for k, v in payload3['options'].items():
        """
        At this point we should have added every supported option
        for the current backend. Iterate through each option and verify
        that it was written to samba's running configuration.
        """
        if k in ['realm', 'ssl']:
            continue

        res = call('smb.getparm', f'{IDMAP_CFG}: {k}', 'GLOBAL')
        assert res is not None, f'Failed to retrieve `{IDMAP_CFG}: {k}` from running configuration'

        if k == 'ldap_url':
            v = f'ldaps://{v}'
        elif k == 'ldap_domain':
            v = None

        if v == 'STANDALONE':
            v = 'stand-alone'

        try:
            res = json.loads(res)
            assert res == v, f"{backend} - [{k}]: {res}"
        except json.decoder.JSONDecodeError:
            if isinstance(v, bool):
                v = str(v)

            if v is None:
                assert res in (None, ''), f"{backend} - [{k}]: {res}"
            else:
                assert v.casefold() == res.casefold(), f"{backend} - [{k}]: {res}"

    if set_secret:
        """
        API calls that set an idmap secret should result in the
        secret being written to secrets.tdb in Samba's private
        directory. To check this, force a secrets db dump, check
        for keys, then decode secret.
        """
        idmap_secret = call('directoryservices.secrets.get_ldap_idmap_secret', WORKGROUP, LDAPBINDDN)
        db_secrets = call('directoryservices.secrets.get_db_secrets')[f'{hostname.upper()}$']

        # Check that our secret is written and stored in secrets backup correctly
        assert idmap_secret == db_secrets[f"SECRETS/GENERIC/IDMAP_LDAP_{WORKGROUP}/{LDAPBINDDN}"]
        decoded_sec = b64decode(idmap_secret).rstrip(b'\x00').decode()
        assert secret == decoded_sec, idmap_secret

        # Use net command via samba to rewrite secret and make sure it is same
        ssh(f"net idmap set secret {WORKGROUP} '{secret}'")
        new_idmap_secret = call('directoryservices.secrets.get_ldap_idmap_secret', WORKGROUP, LDAPBINDDN)
        assert idmap_secret == new_idmap_secret

        secrets_dump = call('directoryservices.secrets.dump')
        assert secrets_dump == db_secrets

    # reset idmap backend to RID to ensure that winbindd is running
    reset_systemd_svcs('winbind smbd')

    payload = {
        "name": "DS_TYPE_ACTIVEDIRECTORY",
        "range_low": "1000000001",
        "range_high": "2000000000",
        "idmap_backend": 'RID',
        "options": {}
    }
    call('idmap.update', 1, payload)


def test_clear_idmap_cache(do_ad_connection):
    call('idmap.clear_idmap_cache', job=True)


def test_idmap_overlap_fail(do_ad_connection):
    """
    It should not be possible to set an idmap range for a new
    domain that overlaps an existing one.
    """
    assert_ad_healthy()
    payload = {
        "name": "canary",
        "range_low": "20000",
        "range_high": "2000000000",
        "idmap_backend": "RID",
        "options": {}
    }
    with pytest.raises(ValidationErrors):
        call('idmap.create', payload)


def test_idmap_default_domain_name_change_fail():
    """
    It should not be possible to change the name of a
    default idmap domain.
    """
    assert_ad_healthy()
    payload = {
        "name": "canary",
        "range_low": "1000000000",
        "range_high": "2000000000",
        "idmap_backend": "RID",
        "options": {}
    }
    with pytest.raises(ValidationErrors):
        call('idmap.create', payload)


def test_idmap_low_high_range_inversion_fail(request):
    """
    It should not be possible to set an idmap low range
    that is greater than its high range.
    """
    assert_ad_healthy()
    payload = {
        "name": "canary",
        "range_low": "2000000000",
        "range_high": "1900000000",
        "idmap_backend": "RID",
    }
    with pytest.raises(ValidationErrors):
        call('idmap.create', payload)


def test_idmap_new_domain_duplicate_fail(idmap_domain):
    """
    It should not be possible to create a new domain that
    has a name conflict with an existing one.
    """
    low, high = call('idmap.get_next_idmap_range')
    payload = {
        "name": idmap_domain["name"],
        "range_low": low,
        "range_high": high,
        "idmap_backend": "RID",
    }
    with pytest.raises(ValidationErrors):
        call('idmap.create', payload)


def test_idmap_new_domain_autorid_fail(idmap_domain):
    """
    It should only be possible to set AUTORID on
    default domain.
    """
    payload = {
        "idmap_backend": "AUTORID",
    }
    with pytest.raises(ValidationErrors):
        call('idmap.update', idmap_domain['id'], payload)

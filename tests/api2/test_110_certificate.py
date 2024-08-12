#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import re
import sys
import os

from time import sleep
from middlewared.test.integration.utils import call
apifolder = os.getcwd()
sys.path.append(apifolder)

try:
    from config import (
        LDAPBASEDN,
        LDAPBINDDN,
        LDAPBINDPASSWORD,
        LDAPHOSTNAME,
    )
except ImportError:
    Reason = 'LDAP* variable are not setup in config.py'
    # comment pytestmark for development testing with --dev-test
    pytestmark = pytest.mark.skipif(True, reason=Reason)


def test_01_get_certificate_query():
    call('certificate.query')


def test_create_idmap_certificate():
    global certificate_id, idmap_id
    payload = {
        "name": "BOB",
        "range_low": 1000,
        "range_high": 2000,
        "certificate": 1,
        "idmap_backend": "RFC2307",
        "options": {
            "ldap_server": "STANDALONE",
            "bind_path_user": LDAPBASEDN,
            "bind_path_group": LDAPBASEDN,
            "ldap_url": LDAPHOSTNAME,
            "ldap_user_dn": LDAPBINDDN,
            "ldap_user_dn_password": LDAPBINDPASSWORD,
            "ssl": "ON",
            "ldap_realm": False,
        }
    }
    results = call("idmap.create", payload)
    idmap_id = results["id"]
    certificate_id = results["certificate"]["id"]


def test_02_delete_used_certificate():
    global job_id
    results = call("certificate.delete", certificate_id, True)
    job_id = int(results)


def test_03_verify_certificate_delete_failed():
    while True:
        get_job = call('core.get_jobs', [["id", "=", job_id]])
        job_status = get_job[0]
        if job_status['state'] in ('RUNNING', 'WAITING'):
            sleep(5)
        else:
            assert job_status['state'] == 'FAILED', get_job
            assert bool(re.search(
                r'Certificate is being used by following service.*IDMAP', job_status['error'], flags=re.DOTALL
            )) is True, job_status['error']
            break


def test_04_delete_idmap():
    call('idmap.delete', [["id", "=", idmap_id]])

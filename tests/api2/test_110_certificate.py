#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, DELETE, POST
from auto_config import dev_test

try:
    from config import (
        LDAPBASEDN,
        LDAPBINDDN,
        LDAPBINDPASSWORD,
        LDAPHOSTNAME,
    )
    # comment pytestmark for development testing with --dev-test
    pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')
except ImportError:
    Reason = 'LDAP* variable are not setup in config.py'
    # comment pytestmark for development testing with --dev-test
    pytestmark = pytest.mark.skipif(True, reason=Reason)


def test_01_get_certificate_query():
    results = GET('/certificate/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


def test_create_idmap_certificate():
    global certificate_id, idmap_id
    payload = {
        'name': 'BOB',
        'range_low': 1000,
        'range_high': 2000,
        'certificate': 1,
        "idmap_backend": "RFC2307",
        'options': {
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
    results = POST('/idmap/', payload)
    assert results.status_code == 200, results.text
    idmap_id = results.json()['id']
    certificate_id = results.json()['certificate']['id']


def test_02_delete_used_certificate():
    global job_id
    results = DELETE(f'/certificate/id/{certificate_id}/', True)
    assert results.status_code == 200, results.text
    job_id = int(results.text)


def test_03_verify_certificate_delete_failed():
    while True:
        get_job = GET(f'/core/get_jobs/?id={job_id}')
        assert get_job.status_code == 200, get_job.text
        job_status = get_job.json()[0]
        if job_status['state'] in ('RUNNING', 'WAITING'):
            sleep(5)
        else:
            assert job_status['state'] == 'FAILED', get_job.text
            try:
                job_status['exc_info']['extra']['dependencies'][0]['objects']
                num = 0
            except KeyError:
                num = 1
            assert job_status['exc_info']['extra']['dependencies'][num]['objects'][0]['certificate']['id'] == certificate_id, get_job.text
            break


def test_04_delete_idmap():
    results = DELETE(f'/idmap/id/{idmap_id}/')
    assert results.status_code == 200, results.text

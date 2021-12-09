#!/usr/bin/env python3

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST
from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')


def test_create_idmap_certificate():
    global idmap_id
    payload = {
        'name': 'BOB.NB',
        'range_low': 1000,
        'range_high': 2000,
        'certificate': 1,
        "idmap_backend": "RFC2307",
        'options': {
            'bind_path_user': '',
            'bind_path_group': '',
            'ldap_domain': '',
            'ldap_url': '',
            'ldap_user_dn': '',
            'ldap_user_dn_password': '',
            'ldap_realm': False,
        }
    }
    results = POST('/idmap/', payload)
    assert results.status_code == 200, results.text
    idmap_id = results.json()['id']


def test_02_delete_used_certificate():
    results = DELETE(f'/idmap/id/{idmap_id}/')
    assert results.status_code == 200, results.text


def test_03_verify_delete_job():
    results = GET(f'/idmap/id/{idmap_id}/')
    assert results.status_code == 404, results.text

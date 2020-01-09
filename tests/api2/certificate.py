#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import sys
import os
from time import sleep
from unittest.mock import ANY
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST


def test_01_get_certificate_query():
    results = GET('/certificate/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


def test_02_delete_used_certificate():
    # FIXME:
    # 1. This really is a test for CRUDService.check_dependencies
    # 2. This idmap API usage looks terribly wrong
    results = POST('/idmap/domain/', {'name': '20191003'})
    assert results.status_code == 200, results.text
    idmap_domain_id = results.json()['id']
    try:
        results = POST('/idmap/rfc2307/', {
            'range_low': 1000,
            'range_high': 2000,
            'domain': {
                'id': idmap_domain_id,
            },
            'bind_path_user': '',
            'bind_path_group': '',
            'ldap_domain': '',
            'ldap_url': '',
            'ldap_user_dn': '',
            'ldap_user_dn_password': '',
            'ldap_realm':'',
            'certificate': 1,
        })
        assert results.status_code == 200, results.text
        idmap_rfc2307_id = results.json()['id']
        try:
            results = DELETE('/certificate/id/1/')
            assert results.status_code == 200, results.text
            job_id = int(results.text)

            while True:
                get_job = GET(f'/core/get_jobs/?id={job_id}')
                assert get_job.status_code == 200, results.text
                job_status = get_job.json()[0]
                if job_status['state'] in ('RUNNING', 'WAITING'):
                    sleep(5)
                else:
                    assert (
                        job_status['state'] == 'FAILED' and
                        job_status['exc_info']['extra'] == {
                            'dependencies': [
                                {
                                    'datastore': 'directoryservice.idmap_rfc2307',
                                    'service': 'idmap.rfc2307',
                                    'objects': [ANY],
                                },
                                {
                                    'datastore': 'system.settings',
                                    'service': 'system.general',
                                    'key': ['guicertificate'],
                                },
                            ]
                        } and
                        job_status['exc_info']['extra']['dependencies'][0]['objects'][0]['id'] == idmap_rfc2307_id,
                    ), get_job.text
                    break
        finally:
            results = DELETE(f'/idmap/rfc2307/id/{idmap_rfc2307_id}/')
            assert results.status_code == 200, results.text
    finally:
        results = DELETE(f'/idmap/domain/id/{idmap_domain_id}/')
        assert results.status_code == 200, results.text

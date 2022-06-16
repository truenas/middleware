#!/usr/bin/env python3

# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
import time
import re
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import user, ip, password, pool_name, ha, dev_test
from functions import GET, POST, PUT, DELETE, SSH_TEST, wait_on_job

reason = 'Skip for test development'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)

# Exclude from HA testing
if not ha:
    JOB_ID = None
    RELEASE = None
    JAIL_NAME = 'jail1'

    @pytest.mark.dependency(name="activate_jail")
    def test_03_activate_iocage_pool(request):
        depends(request, ["pool_04"], scope="session")
        results = POST('/jail/activate/', pool_name)
        assert results.status_code == 200, results.text
        assert results.json() is True, results.text

    @pytest.mark.dependency(name="get_activated_pool")
    def test_04_verify_iocage_pool(request):
        depends(request, ["activate_jail"])
        results = GET('/jail/get_activated_pool/')
        assert results.status_code == 200, results.text
        assert results.json() == pool_name, results.text

    def test_05_get_installed_FreeBSD_release(request):
        depends(request, ["get_activated_pool"])
        results = POST('/jail/releases_choices/', False)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json() == {}, results.text

    @pytest.mark.dependency(name="get_release")
    def test_06_get_available_FreeBSD_release(request):
        depends(request, ["get_activated_pool"])
        global RELEASE
        results = POST('/jail/releases_choices/', True)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        RELEASE = sorted(list(results.json()))[-1]
        assert re.match(r'\d{2}.\d-RELEASE', RELEASE), RELEASE

    @pytest.mark.timeout(600)
    @pytest.mark.dependency(name="fetch_freebsd")
    def test_07_fetch_FreeBSD(request):
        depends(request, ["get_release"])
        results = POST(
            '/jail/fetch/', {
                'release': RELEASE
            }
        )
        assert results.status_code == 200, results.text
        job_status = wait_on_job(results.json(), 600)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_09_verify_FreeBSD_release_is_installed(request):
        depends(request, ["fetch_freebsd"])
        results = POST('/jail/releases_choices', False)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert RELEASE in results.json(), results.text

    @pytest.mark.timeout(600)
    @pytest.mark.dependency(name="create_jail")
    def test_10_create_jail(request):
        depends(request, ["fetch_freebsd"])
        payload = {
            'release': RELEASE,
            'uuid': JAIL_NAME,
            'props': [
                'nat=1',
                'vnet=1',
                'vnet_default_interface=auto'
            ]
        }
        results = POST('/jail/', payload)
        assert results.status_code == 200, results.text
        job_status = wait_on_job(results.json(), 600)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_12_verify_iocage_list_with_ssh(request):
        depends(request, ["ssh_password", "create_jail"], scope="session")
        cmd1 = f'iocage list | grep {JAIL_NAME} | grep -q {RELEASE}'
        results = SSH_TEST(cmd1, user, password, ip)
        cmd2 = 'iocage list'
        results2 = SSH_TEST(cmd2, user, password, ip)
        assert results['result'] is True, results2['output']

    def test_13_update_jail_description(request):
        depends(request, ["create_jail"])
        global JAIL_NAME
        results = PUT(
            f'/jail/id/{JAIL_NAME}/', {
                'name': JAIL_NAME + '_renamed'
            }
        )
        assert results.status_code == 200, results.text
        assert results.json() is True, results.text
        JAIL_NAME += '_renamed'

    def test_14_start_jail(request):
        depends(request, ["create_jail"])
        results = POST('/jail/start/', JAIL_NAME)
        assert results.status_code == 200, results.text
        job_status = wait_on_job(results.json(), 20)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        for run in range(10):
            results = GET(f'/jail/id/{JAIL_NAME}/')
            assert results.status_code == 200, results.text
            if results.json()['state'] == 'up':
                break
            time.sleep(1)
        assert results.json()['state'] == 'up', results.text

    def test_16_exec_call(request):
        depends(request, ["create_jail"])
        results = POST(
            '/jail/exec/', {
                'jail': JAIL_NAME,
                'command': ['echo "exec successful"']
            }
        )
        assert results.status_code == 200, results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        results = job_status['results']['result']
        assert 'exec successful' in results, str(results)

    def test_18_stop_jail(request):
        depends(request, ["create_jail"])
        payload = {
            'jail': JAIL_NAME,
        }
        results = POST('/jail/stop/', payload)
        assert results.status_code == 200, results.text
        job_status = wait_on_job(results.json(), 20)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        for run in range(10):
            results = GET(f'/jail/id/{JAIL_NAME}/')
            assert results.status_code == 200, results.text
            if results.json()['state'] == 'down':
                break
            time.sleep(1)
        assert results.json()['state'] == 'down', results.text

    def test_20_export_jail(request):
        depends(request, ["create_jail"])
        payload = {
            "jail": JAIL_NAME,
            "compression_algorithm": "ZIP"
        }
        results = POST('/jail/export/', payload)
        assert results.status_code == 200, results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_22_start_jail(request):
        depends(request, ["create_jail"])
        results = POST('/jail/start/', JAIL_NAME)
        assert results.status_code == 200, results.text
        job_status = wait_on_job(results.json(), 20)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        for run in range(10):
            results = GET(f'/jail/id/{JAIL_NAME}/')
            assert results.status_code == 200, results.text
            if results.json()['state'] == 'up':
                break
            time.sleep(1)
        assert results.json()['state'] == 'up', results.text

    def test_24_rc_action(request):
        depends(request, ["create_jail"])
        results = POST('/jail/rc_action/', 'STOP')
        assert results.status_code == 200, results.text

    def test_25_delete_jail(request):
        depends(request, ["create_jail"])
        payload = {
            'force': True
        }
        results = DELETE(f'/jail/id/{JAIL_NAME}/', payload)
        assert results.status_code == 200, results.text

    def test_26_verify_the_jail_id_is_delete(request):
        depends(request, ["create_jail"])
        results = GET(f'/jail/id/{JAIL_NAME}/')
        assert results.status_code == 404, results.text

    def test_27_verify_clean_call(request):
        depends(request, ["activate_jail"])
        results = POST('/jail/clean/', 'ALL')
        assert results.status_code == 200, results.text
        assert results.json() is True, results.text

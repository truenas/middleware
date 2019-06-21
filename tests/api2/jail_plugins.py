
import pytest
import sys
import os
import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import pool_name
from functions import GET, POST

IOCAGE_POOL = pool_name
JOB_ID = None
job_info = None
not_freenas = GET("/system/is_freenas/").json() is False
reason = "System is not FreeNAS skip Jails test"
to_skip = pytest.mark.skipif(not_freenas, reason=reason)


@to_skip
def test_01_activate_jail_pool():
    results = POST('/jail/activate/', IOCAGE_POOL)
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


@to_skip
def test_02_verify_jail_pool():
    results = GET('/jail/get_activated_pool/')
    assert results.status_code == 200, results.text
    assert results.json() == IOCAGE_POOL, results.text


@to_skip
def test_03_verify_list_of_instaled_plugin_job_id():
    global JOB_ID
    payload = {
        'resource': 'PLUGIN'
    }
    results = POST('/jail/list_resource/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    JOB_ID = results.json()


@to_skip
def test_04_verify_instaled_plugin_job_id_is_successfull():
    global job_info
    while True:
        info_status = GET(f'/core/get_jobs/?id={JOB_ID}').json()[0]
        if info_status['state'] in ('RUNNING', 'WAITING'):
            sleep(3)
        else:
            assert info_status['state'] == 'SUCCESS', str(info_status)
            break


@to_skip
def test_05_get_list_of_available_plugins_job_id():
    global JOB_ID
    payload = {
        'resource': 'PLUGIN',
        "remote": True
    }
    results = POST('/jail/list_resource/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    JOB_ID = results.json()


@to_skip
def test_06_verify_list_of_available_plugins_job_id_is_successfull():
    global job_info
    while True:
        info_status = GET(f'/core/get_jobs/?id={JOB_ID}').json()[0]
        if info_status['state'] in ('RUNNING', 'WAITING'):
            sleep(3)
        else:
            assert info_status['state'] == 'SUCCESS', str(info_status)
            break

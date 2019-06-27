
import pytest
import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import pool_name
from functions import GET, POST

IOCAGE_POOL = pool_name
JOB_ID = None
job_results = None
not_freenas = GET("/system/is_freenas/").json() is False
reason = "System is not FreeNAS skip Jails test"
to_skip = pytest.mark.skipif(not_freenas, reason=reason)

plugins_list = [
    'asigra',
    'backuppc',
    'bacula-server',
    'bru-server',
    'clamav',
    'couchpotato',
    'deluge',
    'emby',
    'gitlab',
    'irssi ',
    'jenkins',
    'jenkins-lts',
    'madsonic',
    'mineos',
    'nextcloud',
    'plexmediaserver',
    'plexmediaserver-plexpass',
    'qbittorrent',
    'quasselcore',
    'radarr',
    'redmine',
    'rslsync',
    'sonarr',
    'subsonic',
    'syncthing',
    'tarsnap',
    'transmission',
    'weechat',
    'xmrig',
    'zoneminder'
]

plugins_objects = [
    "state",
    "type",
    "release",
]


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
def test_03_get_list_of_instaled_plugin_job_id():
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
    while True:
        job_results = GET(f'/core/get_jobs/?id={JOB_ID}')
        job_state = job_results.json()[0]['state']
        if job_state in ('RUNNING', 'WAITING'):
            sleep(3)
        else:
            assert job_state == 'SUCCESS', str(job_results)
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
    global job_results
    while True:
        job_results = GET(f'/core/get_jobs/?id={JOB_ID}')
        job_state = job_results.json()[0]['state']
        if job_state in ('RUNNING', 'WAITING'):
            sleep(3)
        else:
            assert job_state == 'SUCCESS', str(job_results)
            break


@to_skip
@pytest.mark.parametrize('plugin', plugins_list)
def test_07_verify_available_plugin_(plugin):
    for plugin_info in job_results.json()[0]['result']:
        if plugin in plugin_info:
            assert isinstance(plugin_info, list), job_results.text
            assert plugin in plugin_info, job_results.text


@to_skip
def test_08_add_transmision_plugins():
    global JOB_ID
    payload = {
        "name": "transmission",
        'props': [
            'nat=1',
            'vnet=1',
            'vnet_default_interface=auto'
        ]
    }
    results = POST('/jail/fetch/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


@to_skip
def test_09_verify_transmision_plugin_job_is_successfull():
    while True:
        job_status = GET(f'/core/get_jobs/?id={JOB_ID}').json()[0]
        if job_status['state'] in ('RUNNING', 'WAITING'):
            sleep(3)
        else:
            assert job_status['state'] == 'SUCCESS', str(job_status)
            break


@to_skip
def test_10_verify_transmission_id_jail_exist():
    results = GET('/jail/?id=transmission')
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text


@to_skip
def test_11_looking_transmission_jail_id_is_exist():
    global results
    results = GET('/jail/id/transmission/')
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text


@to_skip
def test_12_get_installed_plugin_list_with_want_cache():
    global JOB_ID
    payload = {
        "resource": "PLUGIN",
        "remote": False,
        "want_cache": True
    }
    results = POST("/jail/list_resource/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    JOB_ID = results.json()


@to_skip
def test_13_verify_list_of_installed_plugins_job_id_is_successfull():
    global job_results
    while True:
        job_results = GET(f'/core/get_jobs/?id={JOB_ID}')
        job_state = job_results.json()[0]['state']
        if job_state in ('RUNNING', 'WAITING'):
            sleep(3)
        else:
            assert job_state == 'SUCCESS', job_results.text
            break


@to_skip
@pytest.mark.parametrize('object', plugins_objects)
def test_14_verify_transmission_plugin_info_value_with_jail_info_value_(object):
    for plugin_list in job_results.json()[0]['result']:
        if 'transmission' in plugin_list['name']:
            assert plugin_list[object] == results.json()[object], plugin_list
            break
    else:
        assert False, job_results.text


@to_skip
def test_15_get_list_of_available_plugins_with_want_cache():
    global JOB_ID
    payload = {
        'resource': 'PLUGIN',
        "remote": True,
        "want_cache": True
    }
    results = POST('/jail/list_resource/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    JOB_ID = results.json()


@to_skip
def test_16_verify_list_of_available_plugins_job_id_is_successfull():
    global job_results
    while True:
        job_results = GET(f'/core/get_jobs/?id={JOB_ID}')
        job_state = job_results.json()[0]['state']
        if job_state in ('RUNNING', 'WAITING'):
            sleep(3)
        else:
            assert job_state == 'SUCCESS', job_results.text
            break


@to_skip
@pytest.mark.parametrize('plugin', plugins_list)
def test_17_verify_available_plugin_with_want_cache_(plugin):
    for plugin_info in job_results.json()[0]['result']:
        if plugin in plugin_info:
            assert isinstance(plugin_info, list), job_results.text
            assert plugin in plugin_info, job_results.text

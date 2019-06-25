
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
job_info = None
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
        job_info = GET(f'/core/get_jobs/?id={JOB_ID}').json()[0]
        if job_info['state'] in ('RUNNING', 'WAITING'):
            sleep(3)
        else:
            assert job_info['state'] == 'SUCCESS', str(job_info)
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
        job_info = GET(f'/core/get_jobs/?id={JOB_ID}').json()[0]
        if job_info['state'] in ('RUNNING', 'WAITING'):
            sleep(3)
        else:
            assert job_info['state'] == 'SUCCESS', str(job_info)
            break


@to_skip
@pytest.mark.parametrize('plugin', plugins_list)
def test_07_verify_available_plugin_(plugin):
    for plugin_info in job_info:
        if plugin in plugin_info:
            assert isinstance(plugin_info, list), job_info.text
            assert plugin in plugin_info, job_info.text


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
def test_10_looking_transmission_jail_id_is_exist():
    results = GET('/jail/id/transmission/')
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text


@to_skip
def test_11_verify_transmission_id_jail_exist():
    global results
    results = GET('/jail/?id=transmission')
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text


@to_skip
def test_10_store_transmission_jail_info():
    assert len(results.json()) > 0, results.text
    global transmission_info
    info = results.json()[0]
    transmission_info = {
        1: info["id"],
        2: info["boot"],
        3: info["state"],
        4: info["type"],
        5: info["release"],
        6: info["ip4_addr"],
    }

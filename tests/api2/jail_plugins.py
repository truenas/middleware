
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
JAIL_NAME = 'Transmission'
RELEASE = "11.2-RELEASE"

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
def test_03_verify_list_of_instaled_plugin():
    payload = {
        'resource': 'PLUGIN'
    }
    results = POST('/jail/list_resource/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


@to_skip
def test_04_get_list_of_available_plugins():
    global results
    payload = {
        'resource': 'PLUGIN',
        "remote": True
    }
    results = POST('/jail/list_resource/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


@to_skip
@pytest.mark.parametrize('plugin', plugins_list)
def test_05_verify_available_plugin_(plugin):
    for plugin_info in results.json():
        if plugin in plugin_info:
            assert isinstance(plugin_info, list), results.text
            assert plugin in plugin_info, results.text


@to_skip
def test_06_add_transmision_plugins():
    global JOB_ID
    payload = {
        "name": "transmission",
        'props': [
            'bpf=yes',
            'dhcp=on',
            'vnet=on',
            'vnet_default_interface=auto'
        ]
    }
    results = POST('/jail/fetch/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


@to_skip
def test_07_verify_transmision_plugin_job_is_successfull():
    while True:
        job_status = GET(f'/core/get_jobs/?id={JOB_ID}').json()[0]
        if job_status['state'] in ('RUNNING', 'WAITING'):
            sleep(3)
        else:
            assert job_status['state'] == 'SUCCESS', str(job_status)
            break


def test_08_verify_transmission_id_jail_exist():
    results = GET('/jail/?id=transmission')
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text


def test_09_get_installed_plugin_list_with_want_cache():
    global results
    payload = {
        "resource": "PLUGIN",
        "remote": False,
        "want_cache": True
    }
    results = POST("/jail/list_resource/", payload).json()
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert len(results.json()) > 0, results.text

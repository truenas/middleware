
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
def test_07_verify_transmision_jail_creation():
    while True:
        job_status = GET(f'/core/get_jobs/?id={JOB_ID}').json()[0]
        if job_status['state'] in ('RUNNING', 'WAITING'):
            sleep(3)
        else:
            results = GET('/jail/')
            assert results.status_code == 200, results.text
            assert len(results.json()) > 0, job_status
            break

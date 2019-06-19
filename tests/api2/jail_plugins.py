
import pytest
import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import pool_name
from functions import GET, POST, DELETE

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
    global results
    results = GET('/jail/?id=transmission')
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text


def test_09_store_transmission_jail_info():
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


def test_10_get_installed_plugin_list_with_want_cache():
    global results
    payload = {
        "resource": "PLUGIN",
        "remote": False,
        "want_cache": True
    }
    results = POST("/jail/list_resource/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert len(results.json()) > 0, results.text


@pytest.mark.parametrize('data', [1, 2, 3, 4, 5, 6])
def test_10_verify_transmission_plugin_info_value_with_jail_info_value_(data):
    for plugin_list in results.json():
        if 'transmission' in plugin_list:
            assert plugin_list[data] == transmission_info[data], plugin_list
            break
    else:
        assert False, results.json()


@to_skip
def test_11_get_list_of_available_plugins_with_want_cache():
    global results
    payload = {
        'resource': 'PLUGIN',
        "remote": True,
        "want_cache": True
    }
    results = POST('/jail/list_resource/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


@to_skip
@pytest.mark.parametrize('plugin', plugins_list)
def test_12_verify_available_plugin_with_want_cache_(plugin):
    for plugin_info in results.json():
        if plugin in plugin_info:
            assert isinstance(plugin_info, list), results.text
            assert plugin in plugin_info, results.text


@to_skip
def test_13_delete_transmission_plugin():
    results = DELETE('/jail/id/transmission/')
    assert results.status_code == 200, results.text

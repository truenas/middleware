
import pytest
import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import pool_name
from functions import GET, POST, DELETE

JOB_ID = None
job_results = None
not_freenas = GET("/system/is_freenas/").json() is False
reason = "System is not FreeNAS skip Jails test"
to_skip = pytest.mark.skipif(not_freenas, reason=reason)
plugin_repos = 'https://github.com/freenas/iocage-ix-plugins.git'

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
    "id",
    "state",
    "type",
    "release",
    "plugin_repository"
]


@to_skip
def test_01_activate_jail_pool():
    results = POST('/jail/activate/', pool_name)
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


@to_skip
def test_02_verify_jail_pool():
    results = GET('/jail/get_activated_pool/')
    assert results.status_code == 200, results.text
    assert results.json() == pool_name, results.text


@to_skip
def test_03_get_list_of_installed_plugin():
    results = GET('/plugin/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


@to_skip
def test_04_verify_plugin_repos_is_in_official_repositories():
    results = GET('/plugin/official_repositories/')
    assert plugin_repos in results.json(), results.text


@to_skip
def test_05_get_list_of_available_plugins_job_id():
    global JOB_ID
    payload = {
        "plugin_repository": plugin_repos
    }
    results = POST('/plugin/available/', payload)
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
        "plugin_name": "transmission",
        "jail_name": "transmission",
        'props': [
            'nat=1',
            'vnet=1',
            'vnet_default_interface=auto'
        ],
        "plugin_repository": plugin_repos,
    }
    results = POST('/plugin/', payload)
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
def test_10_search_plugin_transmission_id():
    results = GET('/plugin/?id=transmission')
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text


@to_skip
def test_11_get_transmission_plugin_info():
    global transmission_plugin
    results = GET('/plugin/id/transmission/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    transmission_plugin = results.json()


@to_skip
def test_12_get_transmission_jail_info():
    global transmission_jail
    results = GET("/jail/id/transmission")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    transmission_jail = results.json()


@to_skip
@pytest.mark.parametrize('object', plugins_objects)
def test_13_verify_transmission_plugin_value_with_jail_value_of_(object):
    assert transmission_jail[object] == transmission_plugin[object], results.text


@to_skip
def test_14_get_list_of_available_plugins_with_cache():
    global JOB_ID
    payload = {
        "plugin_repository": plugin_repos,
        "cache": True
    }
    results = POST('/plugin/available/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    JOB_ID = results.json()


@to_skip
def test_15_verify_list_of_available_plugins_job_id_is_successfull():
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
def test_16_verify_available_plugin_with_want_cache_(plugin):
    for plugin_info in job_results.json()[0]['result']:
        if plugin in plugin_info:
            assert isinstance(plugin_info, list), job_results.text
            assert plugin in plugin_info, job_results.text


@to_skip
def test_17_stop_transmission_jail():
    global results
    payload = {
        "jail": "transmission",
        "force": True
    }
    results = POST('/jail/stop/', payload)
    assert results.status_code == 200, results.text


@to_skip
def test_18_wait_for_transmission_plugin_to_be_down():
    results = GET('/plugin/id/transmission/')
    timeout = 0
    while results.json()['state'] == 'up':
        sleep(1)
        results = GET('/plugin/id/transmission/')
        assert results.status_code == 200, results.text
        if timeout == 10:
            break
        timeout += 1
    assert results.json()['state'] == 'down', results.text


@to_skip
def test_19_start_transmission_jail():
    global results
    payload = "transmission"
    results = POST('/jail/start/', payload)
    assert results.status_code == 200, results.text


@to_skip
def test_20_wait_for_transmission_plugin_to_be_up():
    results = GET('/plugin/id/transmission/')
    timeout = 0
    while results.json()['state'] == 'down':
        sleep(1)
        results = GET('/plugin/id/transmission/')
        assert results.status_code == 200, results.text
        if timeout == 10:
            break
        timeout += 1
    assert results.json()['state'] == 'up', results.text


@to_skip
def test_21_stop_transmission_jail_before_deleteing():
    global results
    payload = {
        "jail": "transmission",
        "force": True
    }
    results = POST('/jail/stop/', payload)
    assert results.status_code == 200, results.text


@to_skip
def test_22_wait_for_transmission_plugin_to_be_down():
    results = GET('/plugin/id/transmission/')
    timeout = 0
    while results.json()['state'] == 'up':
        sleep(1)
        results = GET('/plugin/id/transmission/')
        assert results.status_code == 200, results.text
        if timeout == 10:
            break
        timeout += 1
    assert results.json()['state'] == 'down', results.text


@to_skip
def test_23_delete_transmission_plugin():
    results = DELETE('/plugin/id/transmission/')
    assert results.status_code == 200, results.text


@to_skip
def test_24_looking_transmission_jail_id_is_delete():
    results = GET('/jail/id/transmission/')
    assert results.status_code == 404, results.text


@to_skip
def test_25_looking_transmission_plugin_id_is_delete():
    results = GET('/plugin/id/transmission/')
    assert results.status_code == 404, results.text

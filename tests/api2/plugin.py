
import pytest
import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import pool_name
from functions import GET, POST, DELETE, wait_on_job

JOB_ID = None
job_results = None
not_freenas = GET("/system/is_freenas/").json() is False
reason = "System is not FreeNAS skip Jails test"
to_skip = pytest.mark.skipif(not_freenas, reason=reason)
repos_url = 'https://github.com/freenas/iocage-ix-plugins.git'
index_url = 'https://raw.githubusercontent.com/freenas/iocage-ix-plugins/master/INDEX'

plugin_index = GET(index_url).json()

plugin_list = list(plugin_index.keys())

plugin_objects = [
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
    assert repos_url in results.json(), results.text


@to_skip
def test_05_get_list_of_available_plugins_job_id():
    global JOB_ID
    payload = {
        "plugin_repository": repos_url
    }
    results = POST('/plugin/available/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    JOB_ID = results.json()


@to_skip
def test_06_verify_list_of_available_plugins_job_id_is_successfull():
    global job_results
    job_status = wait_on_job(JOB_ID)
    assert job_status['state'] == 'SUCCESS', job_status['results']
    job_results = job_status['results']


@to_skip
@pytest.mark.parametrize('plugin', plugin_list)
def test_07_verify_available_plugin_(plugin):
    assert isinstance(job_results['result'], list), str(job_results)
    for plugin_info in job_results['result']:
        if plugin in plugin_info:
            assert plugin in plugin_info, str(job_results)
            assert isinstance(plugin_info, dict), str(job_results)


@to_skip
def test_08_add_transmision_plugins():
    global JOB_ID
    payload = {
        "plugin_name": "transmission",
        "jail_name": "transmission",
        'props': [
            'nat=1'
        ],
        "plugin_repository": repos_url,
    }
    results = POST('/plugin/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


@to_skip
def test_09_verify_transmision_plugin_job_is_successfull():
    job_status = wait_on_job(JOB_ID)
    assert job_status['state'] == 'SUCCESS', job_status['results']


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
    global transmission_jail, results
    results = GET("/jail/id/transmission")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    transmission_jail = results.json()


@to_skip
@pytest.mark.parametrize('prop', plugin_objects)
def test_13_verify_transmission_plugin_value_with_jail_value_of_(prop):
    assert transmission_jail[prop] == transmission_plugin[prop], results.text


@to_skip
def test_14_get_list_of_available_plugins_without_cache():
    global JOB_ID
    payload = {
        "plugin_repository": repos_url,
        "cache": False
    }
    results = POST('/plugin/available/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    JOB_ID = results.json()


@to_skip
def test_15_verify_list_of_available_plugins_job_id_is_successfull():
    global job_results
    job_status = wait_on_job(JOB_ID)
    assert job_status['state'] == 'SUCCESS', job_status['results']
    job_results = job_status['results']


@to_skip
@pytest.mark.parametrize('plugin', plugin_list)
def test_16_verify_available_plugin_without_cache_(plugin):
    assert isinstance(job_results['result'], list), str(job_results)
    for plugin_info in job_results['result']:
        if plugin in plugin_info:
            assert plugin in plugin_info, str(job_results)
            assert isinstance(plugin_info, dict), str(job_results)


@to_skip
def test_17_stop_transmission_jail():
    global JOB_ID
    payload = {
        "jail": "transmission",
        "force": True
    }
    results = POST('/jail/stop/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


@to_skip
def test_18_wait_for_transmission_plugin_to_be_down():
    job_status = wait_on_job(JOB_ID)
    assert job_status['state'] == 'SUCCESS', job_status['results']
    results = GET('/plugin/id/transmission/')
    assert results.json()['state'] == 'down', results.text


@to_skip
def test_19_start_transmission_jail():
    global JOB_ID
    payload = "transmission"
    results = POST('/jail/start/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


@to_skip
def test_20_wait_for_transmission_plugin_to_be_up():
    job_status = wait_on_job(JOB_ID)
    assert job_status['state'] == 'SUCCESS', job_status['results']
    results = GET('/plugin/id/transmission/')
    assert results.json()['state'] == 'up', results.text


@to_skip
def test_21_stop_transmission_jail_before_deleteing():
    global JOB_ID
    payload = {
        "jail": "transmission",
        "force": True
    }
    results = POST('/jail/stop/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


@to_skip
def test_22_wait_for_transmission_plugin_to_be_down():
    job_status = wait_on_job(JOB_ID)
    assert job_status['state'] == 'SUCCESS', job_status['results']
    results = GET('/plugin/id/transmission/')
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

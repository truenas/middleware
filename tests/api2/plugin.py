
import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import pool_name
from functions import GET, POST, DELETE, wait_on_job

JOB_ID = None
job_results = None
is_freenas = GET("/system/is_freenas/").json()

# default URL
if is_freenas is True:
    test_repos_url = 'https://github.com/freenas/iocage-ix-plugins.git'
else:
    test_repos_url = 'https://github.com/truenas/iocage-ix-plugins.git'


repos_url = 'https://github.com/freenas/iocage-ix-plugins.git'
index_url = 'https://raw.githubusercontent.com/freenas/iocage-ix-plugins/11.3-RELEASE/INDEX'
plugin_index = GET(index_url).json()
plugin_list = list(plugin_index.keys())

# custom URL
repos_url2 = 'https://github.com/ericbsd/iocage-ix-plugins.git'
index_url2 = 'https://raw.githubusercontent.com/ericbsd/iocage-ix-plugins/11.3-RELEASE/INDEX'
plugin_index2 = GET(index_url2).json()
plugin_list2 = list(plugin_index.keys())

plugin_objects = [
    "id",
    "state",
    "type",
    "release",
    "plugin_repository"
]


def test_01_activate_jail_pool():
    results = POST('/jail/activate/', pool_name)
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


def test_02_verify_jail_pool():
    results = GET('/jail/get_activated_pool/')
    assert results.status_code == 200, results.text
    assert results.json() == pool_name, results.text


def test_03_get_list_of_installed_plugin():
    results = GET('/plugin/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


def test_04_verify_plugin_repos_is_in_official_repositories():
    results = GET('/plugin/official_repositories/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert 'IXSYSTEMS' in results.json(), results.text
    assert results.json()['IXSYSTEMS']['name'] == 'iXsystems', results.text
    assert results.json()['IXSYSTEMS']['git_repository'] == test_repos_url, results.text


def test_05_get_list_of_available_plugins_job_id():
    global JOB_ID
    payload = {
        "plugin_repository": repos_url
    }
    results = POST('/plugin/available/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    JOB_ID = results.json()


def test_06_verify_list_of_available_plugins_job_id_is_successfull():
    global job_results
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_results = job_status['results']


@pytest.mark.parametrize('plugin', plugin_list)
def test_07_verify_available_plugin_(plugin):
    assert isinstance(job_results['result'], list), str(job_results)
    assert plugin in [p['plugin'] for p in job_results['result']], str(job_results['result'])


@pytest.mark.parametrize('prop', ['version', 'revision', 'epoch'])
def test_08_verify_available_plugins_rslsync_is_not_na_with(prop):
    for plugin_info in job_results['result']:
        if 'rslsync' in plugin_info['plugin']:
            break
    assert plugin_info[prop] != 'N/A', str(job_results)


def test_09_add_rslsync_plugins():
    global JOB_ID
    payload = {
        "plugin_name": "rslsync",
        "jail_name": "rslsync",
        'props': [
            'nat=1'
        ],
        "plugin_repository": repos_url,
    }
    results = POST('/plugin/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


def test_10_verify_rslsync_plugin_job_is_successfull():
    job_status = wait_on_job(JOB_ID, 600)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_11_search_plugin_rslsync_id():
    results = GET('/plugin/?id=rslsync')
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text


def test_12_get_rslsync_plugin_info():
    global rslsync_plugin
    results = GET('/plugin/id/rslsync/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    rslsync_plugin = results.json()


@pytest.mark.parametrize('prop', ['version', 'revision', 'epoch'])
def test_13_verify_rslsync_plugin_value_is_not_na_for_(prop):
    assert rslsync_plugin[prop] != 'N/A', str(rslsync_plugin)


@pytest.mark.parametrize('prop', ['version', 'revision', 'epoch'])
def test_14_verify_rslsync_plugins_installed_and_available_value_(prop):
    for plugin_info in job_results['result']:
        if 'rslsync' in plugin_info['plugin']:
            break
    assert plugin_info[prop] == rslsync_plugin[prop], str(plugin_info)


def test_15_get_rslsync_jail_info():
    global rslsync_jail, results
    results = GET("/jail/id/rslsync")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    rslsync_jail = results.json()


@pytest.mark.parametrize('prop', plugin_objects)
def test_16_verify_rslsync_plugin_value_with_jail_value_of_(prop):
    assert rslsync_jail[prop] == rslsync_plugin[prop], results.text


def test_17_get_list_of_available_plugins_without_cache():
    global JOB_ID
    payload = {
        "plugin_repository": repos_url,
        "cache": False
    }
    results = POST('/plugin/available/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    JOB_ID = results.json()


def test_18_verify_list_of_available_plugins_job_id_is_successfull():
    global job_results
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_results = job_status['results']


@pytest.mark.parametrize('plugin', plugin_list)
def test_19_verify_available_plugin_without_cache_(plugin):
    assert isinstance(job_results['result'], list), str(job_results)
    assert plugin in [p['plugin'] for p in job_results['result']], str(job_results['result'])


def test_20_stop_rslsync_jail():
    global JOB_ID
    payload = {
        "jail": "rslsync",
        "force": True
    }
    results = POST('/jail/stop/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


def test_21_wait_for_rslsync_plugin_to_be_down():
    job_status = wait_on_job(JOB_ID, 15)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    results = GET('/plugin/id/rslsync/')
    assert results.json()['state'] == 'down', results.text


def test_22_start_rslsync_jail():
    global JOB_ID
    payload = "rslsync"
    results = POST('/jail/start/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


def test_23_wait_for_rslsync_plugin_to_be_up():
    job_status = wait_on_job(JOB_ID, 15)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    results = GET('/plugin/id/rslsync/')
    assert results.json()['state'] == 'up', results.text


def test_24_stop_rslsync_jail_before_deleteing():
    global JOB_ID
    payload = {
        "jail": "rslsync",
        "force": True
    }
    results = POST('/jail/stop/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


def test_25_wait_for_rslsync_plugin_to_be_down():
    job_status = wait_on_job(JOB_ID, 15)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    results = GET('/plugin/id/rslsync/')
    assert results.json()['state'] == 'down', results.text


def test_26_delete_rslsync_plugin():
    results = DELETE('/plugin/id/rslsync/')
    assert results.status_code == 200, results.text


def test_27_looking_rslsync_jail_id_is_delete():
    results = GET('/jail/id/rslsync/')
    assert results.status_code == 404, results.text


def test_28_looking_rslsync_plugin_id_is_delete():
    results = GET('/plugin/id/rslsync/')
    assert results.status_code == 404, results.text


def test_29_get_list_of_available_plugins_job_id_on_custom_repos():
    global JOB_ID
    payload = {
        "plugin_repository": repos_url,
        "branch": "11.3-RELEASE"
    }
    results = POST('/plugin/available/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    JOB_ID = results.json()


def test_30_verify_list_of_available_plugins_job_id_is_successfull():
    global job_results
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_results = job_status['results']


@pytest.mark.parametrize('plugin', plugin_list2)
def test_31_verify_available_plugin_(plugin):
    assert isinstance(job_results['result'], list), str(job_results)
    assert plugin in [p['plugin'] for p in job_results['result']], str(job_results['result'])


@pytest.mark.parametrize('prop', ['version', 'revision', 'epoch'])
def test_32_verify_available_plugins_rslsync_is_not_na_(prop):
    for plugin_info in job_results['result']:
        if 'rslsync' in plugin_info['plugin']:
            break
    assert plugin_info[prop] != 'N/A', str(job_results)


def test_33_add_rslsync_plugins():
    global JOB_ID
    payload = {
        "plugin_name": "rslsync",
        "jail_name": "rslsync",
        'props': [
            'nat=1'
        ],
        "plugin_repository": repos_url2,
        "branch": "11.3-RELEASE"
    }
    results = POST('/plugin/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


def test_34_verify_rslsync_plugin_job_is_successfull():
    job_status = wait_on_job(JOB_ID, 600)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_35_search_plugin_rslsync_id():
    results = GET('/plugin/?id=rslsync')
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text


def test_36_verify_rslsync_plugin_id_exist():
    results = GET('/plugin/id/rslsync/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_37_verify_the_rslsync_jail_id_exist():
    results = GET(f'/jail/id/rslsync/')
    assert results.status_code == 200, results.text


def test_38_delete_rslsync_jail():
    payload = {
        'force': True
    }
    results = DELETE(f'/jail/id/rslsync/', payload)
    assert results.status_code == 200, results.text


def test_39_verify_the_rslsync_jail_id_is_delete():
    results = GET(f'/jail/id/rslsync/')
    assert results.status_code == 404, results.text


def test_40_verify_clean_call():
    results = POST('/jail/clean/', 'ALL')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text

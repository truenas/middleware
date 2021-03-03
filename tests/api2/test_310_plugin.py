
import os
import pytest
import sys
import time
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import pool_name, ha, scale, ip, user, password, dev_test
from functions import GET, POST, PUT, DELETE, wait_on_job, SSH_TEST

if dev_test:
    reason = 'Skip for testing'
else:
    reason = 'Skipping test for HA' if ha else 'Skipping test for SCALE'
pytestmark = pytest.mark.skipif(ha or scale or dev_test, reason=reason)

JOB_ID = None
job_results = None
default_repos_url = 'https://github.com/freenas/iocage-ix-plugins.git'
community_repos_url = 'https://github.com/ix-plugin-hub/iocage-plugin-index.git'
custom_community_repos_url = 'https://github.com/ericbsd/iocage-plugin-index.git'

if not scale and not ha:
    PUT("/ssh/", {"rootlogin": True}, controller_a=ha)
    POST("/service/start/", {"service": "ssh"}, controller_a=ha)
    ssh_cmd = "uname -r | cut -d '-' -f1"
    release_version = SSH_TEST(ssh_cmd, user, password, ip)['output'].strip()
    community_index_url = f'https://raw.githubusercontent.com/ix-plugin-hub/iocage-plugin-index/{release_version}-RELEASE/INDEX'
    community_plugin_index = GET(community_index_url).json()
    community_plugin_list = list(community_plugin_index.keys())
    custom_community_index_url = f'https://raw.githubusercontent.com/ericbsd/iocage-plugin-index/{release_version}-RELEASE/INDEX'
    custom_community_plugin_index = GET(custom_community_index_url).json()
    custom_community_plugin_list = list(custom_community_plugin_index.keys())
    PUT("/ssh/", {"rootlogin": False}, controller_a=ha)
    POST("/service/stop/", {"service": "ssh"}, controller_a=ha)
else:
    community_plugin_list = []
    custom_community_plugin_list = []


plugin_objects = [
    "id",
    "state",
    "type",
    "release",
    "plugin_repository"
]

default_plugins = [
    'asigra',
    'nextcloud',
    'plexmediaserver',
    'plexmediaserver-plexpass',
    'syncthing',
    'tarsnap',
    'iconik'
]


def test_01_get_nameserver1_and_nameserver2(request):
    depends(request, ["pool_04"], scope="session")
    global nameserver1, nameserver2
    results = GET("/network/configuration/")
    assert results.status_code == 200, results.text
    nameserver1 = results.json()['nameserver1']
    nameserver2 = results.json()['nameserver2']


def test_02_set_nameserver_to_google_dns(request):
    depends(request, ["pool_04"], scope="session")
    global payload
    payload = {
        "nameserver1": '8.8.8.8',
        "nameserver2": '8.8.4.4'
    }
    global results
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    time.sleep(1)


def test_03_activate_jail_pool(request):
    depends(request, ["pool_04"], scope="session")
    results = POST('/jail/activate/', pool_name)
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


def test_04_verify_jail_pool(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/jail/get_activated_pool/')
    assert results.status_code == 200, results.text
    assert results.json() == pool_name, results.text


def test_05_get_list_of_installed_plugin(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/plugin/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


def test_06_verify_plugin_repos_is_in_official_repositories(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/plugin/official_repositories/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert 'IXSYSTEMS' in results.json(), results.text
    assert results.json()['IXSYSTEMS']['name'] == 'iXsystems', results.text
    assert results.json()['IXSYSTEMS']['git_repository'] == default_repos_url, results.text


def test_07_get_list_of_default_plugins_available_job_id(request):
    depends(request, ["pool_04"], scope="session")
    global JOB_ID
    results = POST('/plugin/available/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    JOB_ID = results.json()


def test_08_verify_list_of_available_plugins_job_id_is_successfull(request):
    depends(request, ["pool_04"], scope="session")
    global job_results
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_results = job_status['results']


@pytest.mark.parametrize('plugin', default_plugins)
def test_09_verify_available_plugin_(request, plugin):
    depends(request, ["pool_04"], scope="session")
    assert isinstance(job_results['result'], list), str(job_results)
    assert plugin in [p['plugin'] for p in job_results['result']], str(job_results['result'])


@pytest.mark.parametrize('prop', ['version', 'revision', 'epoch'])
def test_10_verify_available_plugins_plexmediaserver_is_not_na_with(request, prop):
    depends(request, ["pool_04"], scope="session")
    for plugin_info in job_results['result']:
        if 'plexmediaserver' in plugin_info['plugin']:
            break
    assert plugin_info[prop] != 'N/A', str(job_results)


def test_11_add_plexmediaserver_plugin(request):
    depends(request, ["pool_04"], scope="session")
    global JOB_ID
    payload = {
        "plugin_name": "plexmediaserver",
        "jail_name": "plexmediaserver",
        'props': [
            'nat=1'
        ],
        "plugin_repository": default_repos_url
    }
    results = POST('/plugin/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


def test_12_verify_plexmediaserver_plugin_job_is_successfull(request):
    depends(request, ["pool_04"], scope="session")
    job_status = wait_on_job(JOB_ID, 700)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_13_search_plugin_plexmediaserver_id(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/plugin/?id=plexmediaserver')
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text


def test_14_get_plexmediaserver_plugin_info(request):
    depends(request, ["pool_04"], scope="session")
    global plexmediaserver_plugin
    results = GET('/plugin/id/plexmediaserver/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    plexmediaserver_plugin = results.json()


@pytest.mark.parametrize('prop', ['version', 'revision', 'epoch'])
def test_15_verify_plexmediaserver_plugin_value_is_not_na_for_(request, prop):
    depends(request, ["pool_04"], scope="session")
    assert plexmediaserver_plugin[prop] != 'N/A', str(plexmediaserver_plugin)


@pytest.mark.parametrize('prop', ['version', 'revision', 'epoch'])
def test_16_verify_plexmediaserver_plugins_installed_and_available_value_(request, prop):
    for plugin_info in job_results['result']:
        if 'plexmediaserver' in plugin_info['plugin']:
            break
    assert plugin_info[prop] == plexmediaserver_plugin[prop], str(plugin_info)


def test_17_get_plexmediaserver_jail_info(request):
    depends(request, ["pool_04"], scope="session")
    global plexmediaserver_jail, results
    results = GET("/jail/id/plexmediaserver")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    plexmediaserver_jail = results.json()


@pytest.mark.parametrize('prop', plugin_objects)
def test_18_verify_plexmediaserver_plugin_value_with_jail_value_of_(request, prop):
    depends(request, ["pool_04"], scope="session")
    assert plexmediaserver_jail[prop] == plexmediaserver_plugin[prop], results.text


def test_19_get_list_of_available_plugins_without_cache(request):
    depends(request, ["pool_04"], scope="session")
    global JOB_ID
    payload = {
        "plugin_repository": community_repos_url,
        "cache": False
    }
    results = POST('/plugin/available/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    JOB_ID = results.json()


def test_20_verify_list_of_available_plugins_job_id_is_successfull(request):
    depends(request, ["pool_04"], scope="session")
    global job_results
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_results = job_status['results']


@pytest.mark.parametrize('plugin', community_plugin_list)
def test_21_verify_available_plugin_without_cache(request, plugin):
    depends(request, ["pool_04"], scope="session")
    assert isinstance(job_results['result'], list), str(job_results)
    assert plugin in [p['plugin'] for p in job_results['result']], str(job_results['result'])


def test_22_stop_plexmediaserver_jail(request):
    depends(request, ["pool_04"], scope="session")
    global JOB_ID
    payload = {
        "jail": "plexmediaserver",
        "force": True
    }
    results = POST('/jail/stop/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


def test_23_wait_for_plexmediaserver_plugin_to_be_down(request):
    depends(request, ["pool_04"], scope="session")
    job_status = wait_on_job(JOB_ID, 60)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    results = GET('/plugin/id/plexmediaserver/')
    assert results.json()['state'] == 'down', results.text


def test_24_start_plexmediaserver_jail(request):
    depends(request, ["pool_04"], scope="session")
    global JOB_ID
    payload = "plexmediaserver"
    results = POST('/jail/start/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


def test_25_wait_for_plexmediaserver_plugin_to_be_up(request):
    depends(request, ["pool_04"], scope="session")
    job_status = wait_on_job(JOB_ID, 60)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    results = GET('/plugin/id/plexmediaserver/')
    assert results.json()['state'] == 'up', results.text


def test_26_stop_plexmediaserver_jail_before_deleteing(request):
    depends(request, ["pool_04"], scope="session")
    global JOB_ID
    payload = {
        "jail": "plexmediaserver",
        "force": True
    }
    results = POST('/jail/stop/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


def test_27_wait_for_plexmediaserver_plugin_to_be_down(request):
    depends(request, ["pool_04"], scope="session")
    job_status = wait_on_job(JOB_ID, 60)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    results = GET('/plugin/id/plexmediaserver/')
    assert results.json()['state'] == 'down', results.text


def test_28_delete_plexmediaserver_plugin(request):
    depends(request, ["pool_04"], scope="session")
    results = DELETE('/plugin/id/plexmediaserver/')
    assert results.status_code == 200, results.text


def test_29_looking_plexmediaserver_jail_id_is_delete(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/jail/id/plexmediaserver/')
    assert results.status_code == 404, results.text


def test_30_looking_plexmediaserver_plugin_id_is_delete(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/plugin/id/plexmediaserver/')
    assert results.status_code == 404, results.text


def test_31_get_list_of_available_plugins_job_id_on_custom_repos(request):
    depends(request, ["pool_04"], scope="session")
    global JOB_ID
    payload = {
        "plugin_repository": custom_community_repos_url,
        "branch": f'{release_version}-RELEASE'
    }
    results = POST('/plugin/available/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    JOB_ID = results.json()


def test_32_verify_list_of_available_plugins_job_id_is_successfull(request):
    depends(request, ["pool_04"], scope="session")
    global job_results
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_results = job_status['results']


@pytest.mark.parametrize('plugin', custom_community_plugin_list)
def test_33_verify_available_plugin(request, plugin):
    depends(request, ["pool_04"], scope="session")
    assert isinstance(job_results['result'], list), str(job_results)
    assert plugin in [p['plugin'] for p in job_results['result']], str(job_results['result'])


@pytest.mark.parametrize('prop', ['version', 'revision', 'epoch'])
def test_34_verify_available_plugins_transmission_is_not_na_(request, prop):
    depends(request, ["pool_04"], scope="session")
    for plugin_info in job_results['result']:
        if 'transmission' in plugin_info['plugin']:
            break
    assert plugin_info[prop] != 'N/A', str(job_results)


def test_35_add_transmission_plugins(request):
    depends(request, ["pool_04"], scope="session")
    global JOB_ID
    payload = {
        "plugin_name": "transmission",
        "jail_name": "transmission",
        'props': [
            'nat=1'
        ],
        "plugin_repository": custom_community_repos_url,
        "branch": f'{release_version}-RELEASE'
    }
    results = POST('/plugin/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


def test_36_verify_transmission_plugin_job_is_successfull(request):
    depends(request, ["pool_04"], scope="session")
    job_status = wait_on_job(JOB_ID, 600)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_37_search_plugin_transmission_id(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/plugin/?id=transmission')
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text


def test_38_verify_transmission_plugin_id_exist(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/plugin/id/transmission/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_39_verify_the_transmission_jail_id_exist(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/jail/id/transmission/')
    assert results.status_code == 200, results.text


def test_40_delete_transmission_jail(request):
    depends(request, ["pool_04"], scope="session")
    payload = {
        'force': True
    }
    results = DELETE('/jail/id/transmission/', payload)
    assert results.status_code == 200, results.text


def test_41_verify_the_transmission_jail_id_is_delete(request):
    depends(request, ["pool_04"], scope="session")
    results = GET('/jail/id/transmission/')
    assert results.status_code == 404, results.text


def test_42_verify_clean_call(request):
    depends(request, ["pool_04"], scope="session")
    results = POST('/jail/clean/', 'ALL')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


def test_43_configure_setting_domain_hostname_and_dns(request):
    depends(request, ["pool_04"], scope="session")
    global payload
    payload = {
        "nameserver1": nameserver1,
        "nameserver2": nameserver2
    }
    global results
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text

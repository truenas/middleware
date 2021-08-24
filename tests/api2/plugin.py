
import os
import pytest
import sys
import time
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import pool_name, ip, user, password
from functions import GET, POST, PUT, DELETE, wait_on_job, SSH_TEST

JOB_ID = None
job_results = None
is_freenas = GET("/system/is_freenas/").json()
ssh_cmd = "uname -r | cut -d '-' -f1,2"
freebsd_release = SSH_TEST(ssh_cmd, user, password, ip)['output'].strip()
# default URL
test_repos_url = 'https://github.com/freenas/iocage-ix-plugins.git'

repos_url = 'https://github.com/ix-plugin-hub/iocage-plugin-index.git'
index_url = f'https://raw.githubusercontent.com/ix-plugin-hub/iocage-plugin-index/{freebsd_release}/INDEX'
plugin_index = GET(index_url).json()
plugin_list = list(plugin_index.keys())

# custom URL
repos_url2 = 'https://github.com/ericbsd/iocage-plugin-index.git'
index_url2 = f'https://raw.githubusercontent.com/ericbsd/iocage-plugin-index/{freebsd_release}/INDEX'
plugin_index2 = GET(index_url2).json()
plugin_list2 = list(plugin_index2.keys())

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


def test_01_get_nameserver1_and_nameserver2():
    global nameserver1, nameserver2
    results = GET("/network/configuration/")
    assert results.status_code == 200, results.text
    nameserver1 = results.json()['nameserver1']
    nameserver2 = results.json()['nameserver2']


def test_02_set_nameserver_to_google_dns(request):
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


def test_03_activate_jail_pool():
    results = POST('/jail/activate/', pool_name)
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


def test_04_verify_jail_pool():
    results = GET('/jail/get_activated_pool/')
    assert results.status_code == 200, results.text
    assert results.json() == pool_name, results.text


def test_05_get_list_of_installed_plugin():
    results = GET('/plugin/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


def test_06_verify_plugin_repos_is_in_official_repositories():
    results = GET('/plugin/official_repositories/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert 'IXSYSTEMS' in results.json(), results.text
    assert results.json()['IXSYSTEMS']['name'] == 'iXsystems', results.text
    assert results.json()['IXSYSTEMS']['git_repository'] == test_repos_url, results.text


def test_07_get_list_of_default_plugins_available_job_id():
    global job_results
    results = POST('/plugin/available/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_results = job_status['results']


@pytest.mark.parametrize('plugin', default_plugins)
def test_08_verify_available_plugin_(plugin):
    assert isinstance(job_results['result'], list), str(job_results)
    assert plugin in [p['plugin'] for p in job_results['result']], str(job_results['result'])


@pytest.mark.parametrize('prop', ['version', 'revision', 'epoch'])
def test_09_verify_available_plugins_asigra_is_not_na_with(prop):
    for plugin_info in job_results['result']:
        if 'asigra' in plugin_info['plugin']:
            break
    assert plugin_info[prop] != 'N/A', str(job_results)


def test_10_add_asigra_plugin():
    payload = {
        "plugin_name": "asigra",
        "jail_name": "asigra",
        'props': [
            'nat=1'
        ],
        "plugin_repository": test_repos_url
    }
    results = POST('/plugin/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()


def test_12_verify_plexmediaserver_plugin_job_is_successfull():
    job_status = wait_on_job(JOB_ID, 1200)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_11_search_plugin_asigra_id():
    results = GET('/plugin/?id=asigra')
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text


def test_12_get_asigra_plugin_info():
    global asigra_plugin
    results = GET('/plugin/id/asigra/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    asigra_plugin = results.json()


@pytest.mark.parametrize('prop', ['version', 'revision', 'epoch'])
def test_13_verify_asigra_plugin_value_is_not_na_for_(prop):
    assert asigra_plugin[prop] != 'N/A', str(asigra_plugin)


@pytest.mark.parametrize('prop', ['version', 'revision', 'epoch'])
def test_14_verify_asigra_plugins_installed_and_available_value_(prop):
    for plugin_info in job_results['result']:
        if 'asigra' in plugin_info['plugin']:
            break
    assert plugin_info[prop] == asigra_plugin[prop], str(plugin_info)


def test_15_get_asigra_jail_info():
    global asigra_jail, results
    results = GET("/jail/id/asigra")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    asigra_jail = results.json()


@pytest.mark.parametrize('prop', plugin_objects)
def test_16_verify_asigra_plugin_value_with_jail_value_of_(prop):
    assert asigra_jail[prop] == asigra_plugin[prop], results.text


def test_17_get_list_of_available_plugins_without_cache():
    global job_results
    payload = {
        "plugin_repository": repos_url,
        "cache": False
    }
    results = POST('/plugin/available/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_results = job_status['results']


@pytest.mark.parametrize('plugin', plugin_list)
def test_18_verify_available_plugin_without_cache_(plugin):
    assert isinstance(job_results['result'], list), str(job_results)
    assert plugin in [p['plugin'] for p in job_results['result']], str(job_results['result'])


def test_19_stop_asigra_jail():
    payload = {
        "jail": "asigra",
        "force": True
    }
    results = POST('/jail/stop/', payload)
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json(), 60)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    results = GET('/plugin/id/asigra/')
    assert results.json()['state'] == 'down', results.text


def test_20_start_asigra_jail():
    payload = "asigra"
    results = POST('/jail/start/', payload)
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json(), 60)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    results = GET('/plugin/id/asigra/')
    assert results.json()['state'] == 'up', results.text


def test_21_stop_asigra_jail_before_deleteing():
    payload = {
        "jail": "asigra",
        "force": True
    }
    results = POST('/jail/stop/', payload)
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json(), 60)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    results = GET('/plugin/id/asigra/')
    assert results.json()['state'] == 'down', results.text


def test_22_delete_asigra_plugin():
    results = DELETE('/plugin/id/asigra/')
    assert results.status_code == 200, results.text


def test_23_looking_asigra_jail_id_is_delete():
    results = GET('/jail/id/asigra/')
    assert results.status_code == 404, results.text


def test_24_looking_asigra_plugin_id_is_delete():
    results = GET('/plugin/id/asigra/')
    assert results.status_code == 404, results.text


def test_25_get_list_of_available_plugins_job_id_on_custom_repos():
    global job_results
    payload = {
        "plugin_repository": repos_url2,
        "branch": freebsd_release
    }
    results = POST('/plugin/available/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    job_results = job_status['results']


@pytest.mark.parametrize('plugin', plugin_list2)
def test_26_verify_available_plugin_(plugin):
    assert isinstance(job_results['result'], list), str(job_results)
    assert plugin in [p['plugin'] for p in job_results['result']], str(job_results['result'])


@pytest.mark.parametrize('prop', ['version', 'revision', 'epoch'])
def test_27_verify_available_plugins_transmission_is_not_na_(prop):
    for plugin_info in job_results['result']:
        if 'transmission' in plugin_info['plugin']:
            break
    assert plugin_info[prop] != 'N/A', str(job_results)


def test_28_add_transmission_plugins():
    payload = {
        "plugin_name": "transmission",
        "jail_name": "transmission",
        'props': [
            'nat=1'
        ],
        "plugin_repository": repos_url2
    }
    results = POST('/plugin/', payload)
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json(), 600)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_29_search_plugin_transmission_id():
    results = GET('/plugin/?id=transmission')
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text


def test_30_verify_transmission_plugin_id_exist():
    results = GET('/plugin/id/transmission/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_31_verify_the_transmission_jail_id_exist():
    results = GET('/jail/id/transmission/')
    assert results.status_code == 200, results.text


def test_32_delete_transmission_jail():
    payload = {
        'force': True
    }
    results = DELETE('/jail/id/transmission/', payload)
    assert results.status_code == 200, results.text


def test_33_verify_the_transmission_jail_id_is_delete():
    results = GET('/jail/id/transmission/')
    assert results.status_code == 404, results.text


def test_34_verify_clean_call():
    results = POST('/jail/clean/', 'ALL')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


def test_35_configure_setting_domain_hostname_and_dns(request):
    global payload
    payload = {
        "nameserver1": nameserver1,
        "nameserver2": nameserver2
    }
    global results
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text

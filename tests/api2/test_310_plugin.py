
import os
import pytest
import sys
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import pool_name, ha, dev_test
from functions import GET, POST, DELETE, wait_on_job

reason = 'Skip for test development'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)


# Exclude from HA testing
if not ha:
    JOB_ID = None
    job_results = None
    is_freenas = GET("/system/is_freenas/").json()
    test_repos_url = 'https://github.com/freenas/iocage-ix-plugins.git'

    plugins_branch = '13.1-RELEASE'
    repos_url = 'https://github.com/ix-plugin-hub/iocage-plugin-index.git'
    index_url = f'https://raw.githubusercontent.com/ix-plugin-hub/iocage-plugin-index/{plugins_branch}/INDEX'

    plugin_index = GET(index_url).json()
    plugin_list = list(plugin_index.keys())

    # custom URL
    repos_url2 = 'https://github.com/ericbsd/iocage-plugin-index.git'
    index_url2 = f'https://raw.githubusercontent.com/ericbsd/iocage-plugin-index/{plugins_branch}/INDEX'
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

    @pytest.mark.dependency(name="ACTIVATE_JAIL_POOL")
    def test_03_activate_jail_pool(request):
        depends(request, ["pool_04"], scope="session")
        results = POST('/jail/activate/', pool_name)
        assert results.status_code == 200, results.text
        assert results.json() is True, results.text

    def test_04_verify_jail_pool(request):
        depends(request, ["ACTIVATE_JAIL_POOL"])
        results = GET('/jail/get_activated_pool/')
        assert results.status_code == 200, results.text
        assert results.json() == pool_name, results.text

    def test_05_get_list_of_installed_plugin(request):
        depends(request, ["ACTIVATE_JAIL_POOL"])
        results = GET('/plugin/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text

    def test_06_verify_plugin_repos_is_in_official_repositories(request):
        depends(request, ["ACTIVATE_JAIL_POOL"])
        results = GET('/plugin/official_repositories/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert 'IXSYSTEMS' in results.json(), results.text
        assert results.json()['IXSYSTEMS']['name'] == 'iXsystems', results.text
        assert results.json()['IXSYSTEMS']['git_repository'] == test_repos_url, results.text

    def test_07_get_list_of_default_plugins_available_job_id(request):
        depends(request, ["ACTIVATE_JAIL_POOL"])
        global job_results
        results = POST('/plugin/available/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 180)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        job_results = job_status['results']

    @pytest.mark.parametrize('plugin', default_plugins)
    def test_08_verify_available_plugin_(plugin, request):
        depends(request, ["ACTIVATE_JAIL_POOL"])
        assert isinstance(job_results['result'], list), str(job_results)
        assert plugin in [p['plugin'] for p in job_results['result']], str(job_results['result'])

    @pytest.mark.parametrize('prop', ['version', 'revision', 'epoch'])
    def test_09_verify_available_plugins_asigra_is_not_na_with(prop, request):
        depends(request, ["ACTIVATE_JAIL_POOL"])
        for plugin_info in job_results['result']:
            if 'asigra' in plugin_info['plugin']:
                break
        assert plugin_info[prop] != 'N/A', str(job_results)

    @pytest.mark.timeout(1200)
    @pytest.mark.dependency(name="ADD_ASIGRA_PLUGIN")
    def test_10_add_asigra_plugin(request):
        depends(request, ["ACTIVATE_JAIL_POOL"])
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
        job_status = wait_on_job(results.json(), 1200)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_11_search_plugin_asigra_id(request):
        depends(request, ["ADD_ASIGRA_PLUGIN"])
        results = GET('/plugin/?id=asigra')
        assert results.status_code == 200, results.text
        assert len(results.json()) > 0, results.text

    def test_12_get_asigra_plugin_info(request):
        depends(request, ["ADD_ASIGRA_PLUGIN"])
        global asigra_plugin
        results = GET('/plugin/id/asigra/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        asigra_plugin = results.json()

    @pytest.mark.parametrize('prop', ['version', 'revision', 'epoch'])
    def test_13_verify_asigra_plugin_value_is_not_na_for_(prop, request):
        depends(request, ["ADD_ASIGRA_PLUGIN"])
        assert asigra_plugin[prop] != 'N/A', str(asigra_plugin)

    @pytest.mark.parametrize('prop', ['version', 'revision', 'epoch'])
    def test_14_verify_asigra_plugins_installed_and_available_value_(prop, request):
        depends(request, ["ADD_ASIGRA_PLUGIN"])
        for plugin_info in job_results['result']:
            if 'asigra' in plugin_info['plugin']:
                break
        assert plugin_info[prop] == asigra_plugin[prop], str(plugin_info)

    def test_15_get_asigra_jail_info(request):
        depends(request, ["ADD_ASIGRA_PLUGIN"])
        global asigra_jail, results
        results = GET("/jail/id/asigra")
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        asigra_jail = results.json()

    @pytest.mark.parametrize('prop', plugin_objects)
    def test_16_verify_asigra_plugin_value_with_jail_value_of_(prop, request):
        depends(request, ["ADD_ASIGRA_PLUGIN"])
        assert asigra_jail[prop] == asigra_plugin[prop], results.text

    def test_17_get_list_of_available_plugins_without_cache(request):
        depends(request, ["ADD_ASIGRA_PLUGIN"])
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

    def test_19_stop_asigra_jail(request):
        depends(request, ["ADD_ASIGRA_PLUGIN"])
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

    def test_20_start_asigra_jail(request):
        depends(request, ["ADD_ASIGRA_PLUGIN"])
        payload = "asigra"
        results = POST('/jail/start/', payload)
        assert results.status_code == 200, results.text
        job_status = wait_on_job(results.json(), 60)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        results = GET('/plugin/id/asigra/')
        assert results.json()['state'] == 'up', results.text

    def test_21_stop_asigra_jail_before_deleteing(request):
        depends(request, ["ADD_ASIGRA_PLUGIN"])
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

    def test_22_delete_asigra_plugin(request):
        depends(request, ["ADD_ASIGRA_PLUGIN"])
        results = DELETE('/plugin/id/asigra/')
        assert results.status_code == 200, results.text

    def test_23_looking_asigra_jail_id_is_delete(request):
        depends(request, ["ADD_ASIGRA_PLUGIN"])
        results = GET('/jail/id/asigra/')
        assert results.status_code == 404, results.text

    def test_24_looking_asigra_plugin_id_is_delete(request):
        depends(request, ["ADD_ASIGRA_PLUGIN"])
        results = GET('/plugin/id/asigra/')
        assert results.status_code == 404, results.text

    def test_25_get_list_of_available_plugins_job_id_on_custom_repos(request):
        depends(request, ["ACTIVATE_JAIL_POOL"])
        global job_results
        payload = {
            "plugin_repository": repos_url2,
            "branch": plugins_branch
        }
        results = POST('/plugin/available/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 180)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        job_results = job_status['results']

    @pytest.mark.parametrize('plugin', plugin_list2)
    def test_26_verify_available_plugin_(plugin, request):
        depends(request, ["ACTIVATE_JAIL_POOL"])
        assert isinstance(job_results['result'], list), str(job_results)
        assert plugin in [p['plugin'] for p in job_results['result']], str(job_results['result'])

    @pytest.mark.parametrize('prop', ['version', 'revision', 'epoch'])
    def test_27_verify_available_plugins_transmission_is_not_na_(prop, request):
        depends(request, ["ACTIVATE_JAIL_POOL"])
        for plugin_info in job_results['result']:
            if 'transmission' in plugin_info['plugin']:
                break
        assert plugin_info[prop] != 'N/A', str(job_results)

    @pytest.mark.timeout(1200)
    @pytest.mark.dependency(name="ADD_TRANSMISSION_PLUGINS")
    def test_28_add_transmission_plugins(request):
        depends(request, ["ACTIVATE_JAIL_POOL"])
        payload = {
            "plugin_name": "transmission",
            "jail_name": "transmission",
            'props': [
                'nat=1'
            ],
            "branch": plugins_branch,
            "plugin_repository": repos_url2
        }
        results = POST('/plugin/', payload)
        assert results.status_code == 200, results.text
        job_status = wait_on_job(results.json(), 1200)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_29_search_plugin_transmission_id(request):
        depends(request, ["ADD_TRANSMISSION_PLUGINS"])
        results = GET('/plugin/?id=transmission')
        assert results.status_code == 200, results.text
        assert len(results.json()) > 0, results.text

    def test_30_verify_transmission_plugin_id_exist(request):
        depends(request, ["ADD_TRANSMISSION_PLUGINS"])
        results = GET('/plugin/id/transmission/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text

    def test_31_verify_the_transmission_jail_id_exist(request):
        depends(request, ["ADD_TRANSMISSION_PLUGINS"])
        results = GET('/jail/id/transmission/')
        assert results.status_code == 200, results.text

    def test_32_delete_transmission_jail(request):
        depends(request, ["ADD_TRANSMISSION_PLUGINS"])
        payload = {
            'force': True
        }
        results = DELETE('/jail/id/transmission/', payload)
        assert results.status_code == 200, results.text

    def test_33_verify_the_transmission_jail_id_is_delete(request):
        depends(request, ["ADD_TRANSMISSION_PLUGINS"])
        results = GET('/jail/id/transmission/')
        assert results.status_code == 404, results.text

    def test_34_verify_clean_call(request):
        depends(request, ["ACTIVATE_JAIL_POOL"])
        results = POST('/jail/clean/', 'ALL')
        assert results.status_code == 200, results.text
        assert results.json() is True, results.text

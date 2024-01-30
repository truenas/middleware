#!/usr/bin/env python3

import contextlib
import os
import pytest
import sys
import time
from middlewared.test.integration.utils import call
from pytest_dependency import depends
# from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, PUT, POST, DELETE, wait_on_job
from auto_config import ha, interface, ip, pool_name

container_reason = "Can't import docker_username and docker_password"
try:
    from config import (
        docker_username,
        docker_password,
        docker_image,
        docker_tag
    )
    skip_container_image = pytest.mark.skipif(False, reason=container_reason)
except ImportError:
    skip_container_image = pytest.mark.skipif(True, reason=container_reason)

pytestmark = pytest.mark.apps

# Read all the test below only on non-HA
if not ha:
    @contextlib.contextmanager
    def chart_release(app_name, values):
        call(
            "chart.release.create", {
                "catalog": "TRUENAS",
                "item": "ix-chart",
                "release_name": app_name,
                "values": values,
            }, job=True
        )
        while call("chart.release.get_instance", app_name)["status"] != "ACTIVE":
            time.sleep(10)

        chart_release_data = call("chart.release.get_instance", app_name, {"extra": {"retrieve_resources": True}})
        assert_images_exist_for_chart_release(chart_release_data)

        try:
            yield chart_release_data
        finally:
            call("chart.release.delete", app_name, job=True)


    def wait_for_containerd(container_id):
        timeout = 60
        while True:
            if container_id not in [container['id'] for container in call('docker.container.query')]:
                break

            time.sleep(10)
            timeout -= 10
            if timeout <= 0:
                pytest.fail(f'{container_id!r} container was not deleted in 60 seconds')


    def get_num_of_images(images_tags):
        return call(
            "container.image.query", [["OR", [["repo_tags", "rin", tag] for tag in images_tags]]], {"count": True}
        )

    def assert_images_exist_for_chart_release(chart_release_data):
        found_images = get_num_of_images(chart_release_data["resources"]["container_images"])
        assert found_images == len(chart_release_data["resources"]["container_images"])

    def test_pruning_existing_chart_release_images(request):
        depends(request, ['setup_kubernetes'], scope='session')
        with chart_release("prune-test1", {"image": {"repository": "nginx"}}) as chart_release_data:
            call("container.prune", {"remove_unused_images": True}, job=True)
            assert_images_exist_for_chart_release(chart_release_data)
            container_id = chart_release_data['resources']['pods'][0]['status'][
                'containerStatuses'
            ][0]['containerID'].replace('containerd://', '')

        wait_for_containerd(container_id)

    def test_pruning_for_deleted_chart_release_images(request):
        depends(request, ['setup_kubernetes'], scope='session')
        with chart_release("prune-test2", {"image": {"repository": "nginx"}}) as chart_release_data:
            container_images = chart_release_data["resources"]["container_images"]
            container_id = chart_release_data['resources']['pods'][0]['status'][
                'containerStatuses'
            ][0]['containerID'].replace('containerd://', '')
            before_deletion_images = get_num_of_images(container_images)
            assert before_deletion_images != 0

        wait_for_containerd(container_id)
        call("container.prune", {"remove_unused_images": True}, job=True)
        assert get_num_of_images(container_images) == 0

    def test_01_get_container():
        results = GET('/container/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text

    def test_02_change_enable_image_updates_to_false():
        payload = {
            'enable_image_updates': False
        }
        results = PUT('/container/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['enable_image_updates'] is False, results.text

    def test_03_get_container_and_verify_enable_image_updates_is_false():
        results = GET('/container/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['enable_image_updates'] is False, results.text

    def test_04_container_image_query():
        results = GET('/container/image/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text

    @skip_container_image
    @pytest.mark.dependency(name='pull_private_image')
    @pytest.mark.skip(reason='IX network drops network connection routinely.Sometimes, image is not pulled '
                             'successfully.Skipping test until it is fixed')
    def test_05_pull_a_private_container_image(request):
        depends(request, ['setup_kubernetes'], scope='session')
        payload = {
            'authentication': {
                'username': docker_username,
                'password': docker_password
            },
            'from_image': docker_image,
            'tag': docker_tag
        }
        results = POST('/container/image/pull/', payload)
        assert results.status_code == 200, results.text
        job_id = results.json()
        job_status = wait_on_job(job_id, 180)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_06_get_new_private_image_id(request):
        depends(request, ['pull_private_image'])
        global private_image_id
        results = GET('/container/image/')
        for result in results.json():
            if all([f'{docker_image}:{docker_tag}' in tag for tag in result['repo_tags']]):
                private_image_id = result['id']
                assert True, result
                break
        else:
            assert False, results

    def test_07_get_private_image_with_id(request):
        depends(request, ['pull_private_image'])
        results = GET(f'/container/image/id/{private_image_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text

    def test_08_delete_private_image_with_id(request):
        depends(request, ['pull_private_image'])
        results = DELETE(f'/container/image/id/{private_image_id}/')
        assert results.status_code == 200, results.text
        assert results.json() is None, results.text

    def test_09_change_enable_image_updates_to_True():
        payload = {
            'enable_image_updates': True
        }
        results = PUT('/container/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['enable_image_updates'] is True, results

    @pytest.mark.dependency(name='pull_public_image')
    @pytest.mark.skip(reason='IX network drops network connection routinely.Sometimes, image is not pulled '
                             'successfully.Skipping test until it is fixed')
    def test_10_pull_a_public_container_image(request):
        depends(request, ['setup_kubernetes'], scope='session')
        payload = {
            'from_image': 'minio/minio',
            'tag': 'latest'
        }
        results = POST('/container/image/pull/', payload)
        assert results.status_code == 200, results.text
        job_id = results.json()
        job_status = wait_on_job(job_id, 180)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_11_get_new_public_image_id(request):
        depends(request, ['pull_public_image'])
        global public_image_id
        results = GET('/container/image/')
        for result in results.json():
            if result['repo_tags'] == ['docker.io/minio/minio:latest']:
                public_image_id = result['id']
                assert True, result
                break
        else:
            assert False, results

    def test_12_get_public_image_with_id(request):
        depends(request, ['pull_public_image'])
        results = GET(f'/container/image/id/{public_image_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text

    @pytest.mark.dependency(name='tc_chart_release')
    def test_13_create_ix_chart_chart_release_with(request):
        depends(request, ['pull_public_image'])
        global tc_release_id
        payload = {
            'catalog': 'TRUENAS',
            'item': 'ix-chart',
            'release_name': 'minio',
            'train': 'charts',
            'values': {
                'workloadType': 'Deployment',
                'image': {
                    'repository': 'minio/minio',
                    'tag': 'latest'
                },
                'hostNetwork': False
            }
        }
        results = POST('/chart/release/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        tc_release_id = job_status['results']['result']['id']

    def test_14_get_minio_ix_chart_catalog(request):
        depends(request, ['tc_chart_release'])
        results = GET(f'/chart/release/id/{tc_release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['catalog'] == 'TRUENAS', results.text

    def test_15_get_minio_ix_chart_train(request):
        depends(request, ['tc_chart_release'])
        results = GET(f'/chart/release/id/{tc_release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['catalog_train'] == 'charts', results.text

    def test_16_get_minio_ix_chart_name(request):
        depends(request, ['tc_chart_release'])
        results = GET(f'/chart/release/id/{tc_release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['name'] == 'minio', results.text

    def test_17_verify_ix_chart_config_workloadtype(request):
        depends(request, ['tc_chart_release'])
        results = GET(f'/chart/release/id/{tc_release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['config']['workloadType'] == 'Deployment', results.text

    def test_18_verify_ix_chart_config_hostnetwork_is_False(request):
        depends(request, ['tc_chart_release'])
        results = GET(f'/chart/release/id/{tc_release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['config']['hostNetwork'] is False, results.text

    def test_19_verify_ix_chart_config_image(request):
        depends(request, ['tc_chart_release'])
        results = GET(f'/chart/release/id/{tc_release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['config']['image']['repository'] == 'minio/minio', results.text
        assert results.json()['config']['image']['tag'] == 'latest', results.text

    def test_20_set_ix_chart_chart_release_scale_up(request):
        depends(request, ['tc_chart_release'])
        payload = {
            'release_name': 'minio',
            'scale_options': {
                'replica_count': 1
            }
        }
        results = POST('/chart/release/scale/', payload)
        assert results.status_code == 200, results.text
        job_id = results.json()
        job_status = wait_on_job(job_id, 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        results = job_status['results']['result']
        assert isinstance(results, dict), str(job_status['results'])

    def test_21_verify_truecomand_ix_chart_pod_status_desired_is_a_number(request):
        depends(request, ['tc_chart_release'])
        results = GET(f'/chart/release/id/{tc_release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert isinstance(results.json()['pod_status']['desired'], int), results.text

    @pytest.mark.dependency(name='tc_externalInterfaces')
    def test_22_set_externalInterfaces(request):
        depends(request, ['tc_chart_release'])
        global gateway
        gateway = GET('/network/general/summary/').json()['default_routes'][0]
        payload = {
            'values': {
                'externalInterfaces': [
                    {
                        'hostInterface': f'{interface}',
                        'ipam': {
                            'type': 'static',
                            'staticIPConfigurations': [f'{ip}/24'],
                            'staticRoutes': [
                                {
                                    'destination': '0.0.0.0/0',
                                    'gateway': gateway
                                }
                            ]
                        }
                    }
                ]
            }
        }
        results = PUT(f'/chart/release/id/{tc_release_id}/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_23_verify_ix_chart_config_externalInterfaces_hostinterface(request):
        depends(request, ['tc_externalInterfaces'])
        results = GET(f'/chart/release/id/{tc_release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        externalInterfaces = results.json()['config']['externalInterfaces']
        assert externalInterfaces[0]['hostInterface'] == interface, results.text

    def test_24_verify_ix_chart_config_externalInterfaces_interface(request):
        depends(request, ['tc_externalInterfaces'])
        results = GET(f'/chart/release/id/{tc_release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        ipam = results.json()['config']['externalInterfaces'][0]['ipam']
        assert f'{ip}/24' in ipam['staticIPConfigurations'], results.text
        assert {'destination': '0.0.0.0/0', 'gateway': gateway} in ipam['staticRoutes'], results.text
        assert ipam['type'] == 'static', results.text

    def test_25_pull_container_images_and_set_redeploy_to_true(request):
        depends(request, ['tc_chart_release'])
        payload = {
            'release_name': 'minio',
            'pull_container_images_options': {
                'redeploy': True
            }
        }
        results = POST('/chart/release/pull_container_images/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    @pytest.mark.dependency(name='tc_portforwarding')
    def test_26_set_minio_ix_chart_portforwarding(request):
        depends(request, ['tc_chart_release'])
        payload = {
            'values': {
                'portForwardingList': [
                    {
                        'containerPort': 9000,
                        'nodePort': 20345,
                        'protocol': 'TCP'
                    }
                ]
            }
        }
        results = PUT(f'/chart/release/id/{tc_release_id}/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_27_verify_ix_chart_config_portforwardinglist(request):
        depends(request, ['tc_portforwarding'])
        results = GET(f'/chart/release/id/{tc_release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        portForwardingList = results.json()['config']['portForwardingList'][0]
        assert portForwardingList['containerPort'] == 9000, results.text
        assert portForwardingList['nodePort'] == 20345, results.text
        assert portForwardingList['protocol'] == 'TCP', results.text

    @pytest.mark.dependency(name='tc_updatestrategy')
    def test_28_change_minio_ix_chart_updatestrategy_to_recreate(request):
        depends(request, ['tc_chart_release'])
        payload = {
            'values': {
                'updateStrategy': 'Recreate'
            }
        }
        results = PUT(f'/chart/release/id/{tc_release_id}/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_29_verify_ix_chart_config_updatestrategy_is_changed_to_reccireate(request):
        depends(request, ['tc_updatestrategy'])
        results = GET(f'/chart/release/id/{tc_release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['config']['updateStrategy'] == 'Recreate', results.text

    @pytest.mark.dependency(name='tc_dnsConfig')
    def test_30_set_minio_ix_chart_dnsConfig(request):
        depends(request, ['tc_chart_release'])
        global nameservers_list
        results = GET('/network/general/summary/')
        assert isinstance(results.json()['nameservers'], list), results.text
        nameservers_list = results.json()['nameservers'][:2]
        payload = {
            'values': {
                'dnsConfig': {
                    'nameservers': nameservers_list,
                    'searches': []
                },
            }
        }
        results = PUT(f'/chart/release/id/{tc_release_id}/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_31_verify_ix_chart_config_dnsConfig(request):
        depends(request, ['tc_dnsConfig'])
        results = GET(f'/chart/release/id/{tc_release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        dnsConfig = results.json()['config']['dnsConfig']
        assert dnsConfig['nameservers'] == nameservers_list, results.text
        assert dnsConfig['searches'] == [], results.text

    @pytest.mark.dependency(name='tc_livenessProbe')
    def test_32_set_minio_ix_chart_livenessProbe(request):
        depends(request, ['tc_chart_release'])
        payload = {
            'values': {
                'livenessProbe': {
                    'command': ['ls /usr/share'],
                    'initialDelaySeconds': 10,
                    'periodSeconds': 15
                }
            }
        }
        results = PUT(f'/chart/release/id/{tc_release_id}/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_33_verify_ix_chart_config_livenessProbe(request):
        depends(request, ['tc_livenessProbe'])
        results = GET(f'/chart/release/id/{tc_release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        livenessProbe = results.json()['config']['livenessProbe']
        assert 'ls /usr/share' in livenessProbe['command'], results.text
        assert livenessProbe['initialDelaySeconds'] == 10, results.text
        assert livenessProbe['periodSeconds'] == 15, results.text

    @pytest.mark.dependency(name='tc_containerCAE')
    def test_34_set_minio_ix_chart_tc_container_Command_Args_EnvironmentVariables(request):
        depends(request, ['tc_chart_release'])
        payload = {
            'values': {
                'containerCommand': ['sleep'],
                'containerArgs': ['infinity'],
                'containerEnvironmentVariables': [
                    {
                        'name': 'Eric_Var',
                        'value': 'Something'
                    }
                ]
            }
        }
        results = PUT(f'/chart/release/id/{tc_release_id}/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_35_verify_ix_chart_config_container_Command_Args_EnvironmentVariables(request):
        depends(request, ['tc_containerCAE'])
        results = GET(f'/chart/release/id/{tc_release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        config = results.json()['config']
        assert 'sleep' in config['containerCommand'], results.text
        assert 'infinity' in config['containerArgs'], results.text
        assert {'name': 'Eric_Var', 'value': 'Something'} in config['containerEnvironmentVariables'], results.text

    @pytest.mark.dependency(name='hostpath-dataset')
    def test_36_create_datasets_hostpath(request):
        result = POST('/pool/dataset/', {'name': f'{pool_name}/tc-hostpath'})
        assert result.status_code == 200, result.text

    @pytest.mark.dependency(name='tc_volumes')
    def test_37_set_minio_ix_chart_volumes(request):
        depends(request, ['tc_chart_release'])
        global payload
        payload = {
            'values': {
                'volumes': [
                    {
                        'mountPath': '/mnt',
                        'datasetName': 'tc-mountpath'
                    }
                ]
            }
        }
        results = PUT(f'/chart/release/id/{tc_release_id}/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_38_verify_ix_chart_config_volumes(request):
        depends(request, ['tc_volumes'])
        results = GET(f'/chart/release/id/{tc_release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        payload_volume = payload['values']['volumes'][0]
        assert payload_volume in results.json()['config']['volumes'], results.text

    @pytest.mark.dependency(name='tc_hostPathVolumes')
    def test_39_set_minio_ix_chart_hostPathVolumes(request):
        depends(request, ['tc_chart_release', 'hostpath-dataset'])
        global payload
        payload = {
            'values': {
                'hostPathVolumes': [
                    {
                        'hostPath': f'/mnt/{pool_name}/tc-hostpath',
                        'mountPath': '/mnt',
                        'readOnly': True
                    }
                ]
            }
        }
        results = PUT(f'/chart/release/id/{tc_release_id}/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        time.sleep(1)

    def test_40_verify_ix_chart_config_hostPathVolumes(request):
        depends(request, ['tc_hostPathVolumes'])
        results = GET(f'/chart/release/id/{tc_release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        payload_hostPathVolumes = payload['values']['hostPathVolumes'][0]
        config = results.json()['config']
        assert payload_hostPathVolumes in config['hostPathVolumes'], results.text

    def test_41_verify_ix_chart_resources_host_path_volumes(request):
        depends(request, ['tc_hostPathVolumes'])
        payload = {
            'query-options': {
                'extra': {
                    'retrieve_resources': True
                }
            },
            'query-filters': [['id', '=', tc_release_id]]
        }
        results = GET('/chart/release/', payload)
        host_path_volumes = str(results.json()[0]['resources']['host_path_volumes'])
        assert f'/mnt/{pool_name}/tc-hostpath' in host_path_volumes, host_path_volumes

    def test_42_delete_minio_chart_release(request):
        depends(request, ['tc_chart_release'])
        results = DELETE(f'/chart/release/id/{tc_release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_43_delete_datasets_hostpath_and_mountpath(request):
        depends(request, ['hostpath-dataset'])
        result = DELETE(f'/pool/dataset/id/{pool_name}%2Ftc-hostpath/', {'recursive': True})
        assert result.status_code == 200, result.text

    def test_44_delete_public_image_with_id(request):
        depends(request, ['pull_public_image'])
        results = DELETE(f'/container/image/id/{public_image_id}/')
        assert results.status_code == 200, results.text
        assert results.json() is None, results.text

    def test_45_verify_the_public_image_id_is_deleted(request):
        depends(request, ['pull_public_image'])
        results = GET(f'/container/image/id/{public_image_id}/')
        assert results.status_code == 404, results.text
        assert isinstance(results.json(), dict), results.text

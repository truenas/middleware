#!/usr/bin/env python3

import os
import pytest
import sys
from pytest_dependency import depends
# from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, PUT, POST, DELETE, wait_on_job
from auto_config import ha, scale, dev_test

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


if dev_test:
    reason = 'Skip for testing'
else:
    reason = 'Skipping test for HA' if ha else 'Skipping test for CORE'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(ha or not scale or dev_test, reason=reason)


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


def test_04_get_pull_container_image():
    results = GET('/container/image/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


@skip_container_image
@pytest.mark.dependency(name='pull_private_image')
def test_05_pull_a_private_container_image(request):
    depends(request, ["setup_kubernetes"], scope="session")
    payload = {
        "docker_authentication": {
            "username": docker_username,
            "password": docker_password
        },
        "from_image": docker_image,
        "tag": docker_tag
    }
    results = POST('/container/image/pull/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_06_get_new_private_image_id(request):
    depends(request, ["pull_private_image"])
    global private_image_id
    results = GET("/container/image/")
    for result in results.json():
        if result['repo_tags'] == [f'{docker_image}:{docker_tag}']:
            private_image_id = result['id']
            assert True, result
            break
    else:
        assert False, results


def test_07_get_private_image_with_id(request):
    depends(request, ["pull_private_image"])
    results = GET(f'/container/image/id/{private_image_id}/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_08_change_enable_image_updates_to_True():
    payload = {
        'enable_image_updates': True
    }
    results = PUT('/container/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['enable_image_updates'] is True, results


@pytest.mark.dependency(name='pull_public_image')
def test_09_pull_a_public_container_image(request):
    depends(request, ["setup_kubernetes"], scope="session")
    payload = {
        "from_image": 'ixsystems/truecommand',
        "tag": 'latest'
    }
    results = POST('/container/image/pull/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_10_get_new_public_image_id(request):
    depends(request, ["pull_public_image"])
    global public_image_id
    results = GET("/container/image/")
    for result in results.json():
        if result['repo_tags'] == ['ixsystems/truecommand:latest']:
            public_image_id = result['id']
            assert True, result
            break
    else:
        assert False, results


def test_11_get_public_image_with_id(request):
    depends(request, ["pull_public_image"])
    results = GET(f'/container/image/id/{public_image_id}/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_12_delete_private_image_with_id(request):
    depends(request, ["pull_private_image"])
    results = DELETE(f'/container/image/id/{private_image_id}/')
    assert results.status_code == 200, results.text
    assert results.json() is None, results.text


def test_13_verify_the_private_image_id_is_deleted(request):
    depends(request, ["pull_private_image"])
    results = GET(f'/container/image/id/{private_image_id}/')
    assert results.status_code == 404, results.text
    assert isinstance(results.json(), dict), results.text


def test_14_delete_public_image_with_id(request):
    depends(request, ["pull_public_image"])
    results = DELETE(f'/container/image/id/{public_image_id}/')
    assert results.status_code == 200, results.text
    assert results.json() is None, results.text


def test_15_verify_the_public_image_id_is_deleted(request):
    depends(request, ["pull_public_image"])
    results = GET(f'/container/image/id/{public_image_id}/')
    assert results.status_code == 404, results.text
    assert isinstance(results.json(), dict), results.text

#!/usr/bin/env python3

import os
import pytest
import sys
# from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, PUT, POST, wait_on_job
from auto_config import ha, scale

container_reason = "Can't import docker_username and docker_password"
try:
    from config import docker_username, docker_password
    skip_container_image = pytest.mark.skipif(False, reason=container_reason)
except ImportError:
    skip_container_image = pytest.mark.skipif(True, reason=container_reason)


reason = 'Skipping test for HA' if ha else 'Skipping test for CORE'
pytestmark = pytest.mark.skipif(ha or not scale, reason=reason)


def test_01_get_container(request):
    results = GET('/container/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_02_change_enable_image_updates_to_false(request):
    payload = {
        'enable_image_updates': False
    }
    results = PUT('/container/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['enable_image_updates'] is False, results.text


def test_03_get_container_and_verify_enable_image_updates_is_false(request):
    results = GET('/container/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['enable_image_updates'] is False, results.text


def test_04_get_pull_container_image(request):
    results = GET('/container/image/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


@skip_container_image
def test_05_pull_container_image(request):
    payload = {
        "docker_authentication": {
            "username": docker_username,
            "password": docker_password
        },
        "from_image": "ixsystems/truecommand-internal",
        "tag": "latest"
    }
    results = POST('/container/image/pull/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

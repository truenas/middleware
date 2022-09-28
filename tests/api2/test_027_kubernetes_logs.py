#!/usr/bin/env python3

import contextlib
import os
from time import sleep
import pytest
import sys

from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from middlewared.test.integration.utils import call, ssh
from auto_config import ip


@contextlib.contextmanager
def official_chart_release(chart_name, release_name):
    payload = {
        'catalog': 'OFFICIAL',
        'item': chart_name,
        'release_name': release_name,
        'train': 'charts',
    }
    chart_release = call('chart.release.create', payload, job=True)
    try:
        yield chart_release
    finally:
        call('chart.release.delete', release_name, job=True)


@contextlib.contextmanager
def get_chart_release_pods(release_name, timeout=90):
    status = call('chart.release.pod_status', release_name)
    time_spend = 0
    while status.get('status') != 'ACTIVE':
        if time_spend > timeout:
            raise Exception("Time out chart release is not in running state")
        sleep(6)
        time_spend += 6
        status = call('chart.release.pod_status', release_name)

    # Give some time for the pods to actually propagate some logs
    sleep(10)
    chart_pods = call('chart.release.pod_logs_choices', release_name)
    yield chart_pods


def test_get_chart_release_logs(request):
    depends(request, ['setup_kubernetes'], scope='session')
    release_name = 'test-logs'
    with official_chart_release('qbittorent', release_name) as chart_release:
        with get_chart_release_pods(release_name, 300) as pods:
            for pod_name, containers in pods.items():
                for container in containers:
                    logs = call('k8s.pod.get_logs', pod_name, container, chart_release['namespace'])
                    assert logs != ''


def test_get_chart_exec_result(request):
    depends(request, ['setup_kubernetes'], scope='session')
    release_name = 'test-exec'
    with official_chart_release('qbittorent', release_name) as chart_release:
        with get_chart_release_pods(release_name, 300) as pods:
            for pod_name, containers in pods.items():
                for container in containers:
                    result = ssh(
                        f'k3s kubectl exec -n {chart_release["namespace"]} pods/{pod_name} -c {container} -- /bin/ls',
                        check=False)
                    assert result != ''

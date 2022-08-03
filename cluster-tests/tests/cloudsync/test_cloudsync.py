import pytest

from middlewared.client import ClientException
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.cloud_sync import *

from config import CLUSTER_INFO, CLUSTER_IPS
from utils import make_request, ssh_test, wait_on_job

LOCAL_PATH = f'/cluster/{CLUSTER_INFO["GLUSTER_VOLUME"]}/cloudsync_01'
CLUSTER_PATH = f'CLUSTER:{CLUSTER_INFO["GLUSTER_VOLUME"]}/cloudsync_01'


def test_works():
    res = ssh_test(CLUSTER_IPS[0], f'mkdir {LOCAL_PATH}')
    assert res['result'], res['stderr']
    try:
        res = ssh_test(CLUSTER_IPS[0], f'echo test > {LOCAL_PATH}/file01')
        assert res['result'], res['stderr']

        try:
            with local_s3_task({
                "path": CLUSTER_PATH,
            }) as task:
                run_task(task)

                res = ssh_test(CLUSTER_IPS[0], f'cat {LOCAL_PATH}/file01')
                assert res['result'], res['stderr']

                assert res['output'] == 'test\n'
        finally:
            res = ssh_test(CLUSTER_IPS[0], f'rm -rf {LOCAL_PATH}')
            assert res['result'], res['stderr']
    finally:
        res = ssh_test(CLUSTER_IPS[0], f'rm -rf {LOCAL_PATH}')
        assert res['result'], res['stderr']


def test_invalid_cluster_path():
    with pytest.raises(ClientException) as e:
        with local_s3_task({
            "path": CLUSTER_PATH,
        }) as task:
            run_task(task)

    assert str(e.value) == f"[EFAULT] Directory '{CLUSTER_PATH}' does not exist"


def test_cluster_path_snapshot():
    with pytest.raises(ValidationErrors) as e:
        with local_s3_task({
            "path": CLUSTER_PATH,
            "snapshot": True
        }):
            pass

    assert str(e.value) == f"[EINVAL] cloud_sync_create.snapshot: This option can not be used for cluster paths\n"

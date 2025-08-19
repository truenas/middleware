import pytest

from truenas_api_client import ClientException
from middlewared.test.integration.assets.cloud_sync import local_ftp_task, run_task
from middlewared.test.integration.utils import call, ssh


def test_pre_script_failure():
    with local_ftp_task({
        "pre_script": "echo Custom error\nexit 123",
    }) as task:
        with pytest.raises(ClientException) as ve:
            run_task(task)

        assert ve.value.error == "[EFAULT] Pre-script failed with exit code 123"

        job = call("core.get_jobs", [["method", "=", "cloudsync.sync"]], {"order_by": ["-id"], "get": True})
        assert job["logs_excerpt"] == "[Pre-script] Custom error\n"


def test_pre_script_ok():
    ssh("rm /tmp/cloud_sync_test", check=False)
    with local_ftp_task({
        "pre_script": "touch /tmp/cloud_sync_test",
    }) as task:
        run_task(task)

        ssh("cat /tmp/cloud_sync_test")


def test_post_script_not_running_after_failure():
    ssh("touch /tmp/cloud_sync_test")
    with local_ftp_task({
        "post_script": "rm /tmp/cloud_sync_test",
    }) as task:
        call("service.control", "STOP", "ftp", job=True)

        with pytest.raises(ClientException) as ve:
            run_task(task)

        assert "connection refused" in ve.value.error

        ssh("cat /tmp/cloud_sync_test")


def test_post_script_ok():
    ssh("rm /tmp/cloud_sync_test", check=False)
    with local_ftp_task({
        "post_script": "touch /tmp/cloud_sync_test",
    }) as task:
        run_task(task)

        ssh("cat /tmp/cloud_sync_test")


def test_script_shebang():
    with local_ftp_task({
        "post_script": "#!/usr/bin/env python3\nprint('Test' * 2)",
    }) as task:
        run_task(task)

        job = call("core.get_jobs", [["method", "=", "cloudsync.sync"]], {"order_by": ["-id"], "get": True})
        assert job["logs_excerpt"].endswith("[Post-script] TestTest\n")

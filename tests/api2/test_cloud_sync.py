import contextlib
import re
import time

import pytest

from middlewared.test.integration.assets.cloud_sync import credential, task, local_s3_credential, local_s3_task
from middlewared.test.integration.assets.ftp import anonymous_ftp_server, ftp_server_with_user_account
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, pool, ssh

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE
from auto_config import dev_test
reason = 'Skip for testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)


def run_task(task):
    result = POST(f"/cloudsync/id/{task['id']}/sync/")
    assert result.status_code == 200, result.text
    for i in range(120):
        result = GET(f"/cloudsync/id/{task['id']}/")
        assert result.status_code == 200, result.text
        state = result.json()
        if state["job"] is None:
            time.sleep(1)
            continue
        if state["job"]["state"] in ["WAITING", "RUNNING"]:
            time.sleep(1)
            continue
        assert state["job"]["state"] == "SUCCESS", state
        return

    assert False, state


def test_include():
    with local_s3_task({
        "include": ["/office/**", "/work/**"],
    }) as task:
        ssh(f'mkdir {task["path"]}/office')
        ssh(f'touch {task["path"]}/office/paper')
        ssh(f'mkdir {task["path"]}/work')
        ssh(f'touch {task["path"]}/work/code')
        ssh(f'mkdir {task["path"]}/games')
        ssh(f'touch {task["path"]}/games/minecraft')
        ssh(f'touch {task["path"]}/fun')

        run_task(task)

        assert ssh(f'ls /mnt/{pool}/cloudsync_remote/bucket') == 'office\nwork\n'


def test_exclude_recycle_bin():
    with local_s3_task({
        "exclude": ["$RECYCLE.BIN/"],
    }) as task:
        ssh(f'mkdir {task["path"]}/\'$RECYCLE.BIN\'')
        ssh(f'touch {task["path"]}/\'$RECYCLE.BIN\'/garbage')
        ssh(f'touch {task["path"]}/file')

        run_task(task)

        assert ssh(f'ls /mnt/{pool}/cloudsync_remote/bucket') == 'file\n'


@pytest.mark.flaky(reruns=5, reruns_delay=5)
@pytest.mark.parametrize("anonymous", [True, False])
@pytest.mark.parametrize("defaultroot", [True, False])
@pytest.mark.parametrize("has_leading_slash", [True, False])
def test_ftp_subfolder(anonymous, defaultroot, has_leading_slash):
    with dataset("cloudsync_local") as local_dataset:
        config = {"defaultroot": defaultroot}
        with (anonymous_ftp_server if anonymous else ftp_server_with_user_account)(config) as ftp:
            remote_dataset = ftp.dataset
            ssh(f"touch /mnt/{remote_dataset}/bad-file")
            ssh(f"mkdir /mnt/{remote_dataset}/data")
            ssh(f"touch /mnt/{remote_dataset}/data/another-bad-file")
            ssh(f"mkdir /mnt/{remote_dataset}/data/child")
            ssh(f"touch /mnt/{remote_dataset}/data/child/good-file")

            with credential({
                "name": "Test",
                "provider": "FTP",
                "attributes": {
                    "host": "localhost",
                    "port": 21,
                    "user": ftp.username,
                    "pass": ftp.password,
                },
            }) as c:
                folder = f"{'/' if has_leading_slash else ''}data/child"
                if not anonymous and not defaultroot:
                    # We have access to the FTP server root directory
                    if has_leading_slash:
                        # A path with a leading slash should be complete path in this case
                        folder = f"/mnt/{ftp.dataset}/data/child"

                with task({
                    "direction": "PULL",
                    "transfer_mode": "MOVE",
                    "path": f"/mnt/{local_dataset}",
                    "credentials": c["id"],
                    "attributes": {
                        "folder": folder,
                    },
                }) as t:
                    run_task(t)

                    assert ssh(f'ls /mnt/{local_dataset}') == 'good-file\n'


@pytest.mark.parametrize("has_zvol_sibling", [True, False])
def test_snapshot(has_zvol_sibling):
    with dataset("test") as ds:
        ssh(f"mkdir -p /mnt/{ds}/dir1/dir2")
        ssh(f"dd if=/dev/urandom of=/mnt/{ds}/dir1/dir2/blob bs=1M count=1")

        if has_zvol_sibling:
            ssh(f"zfs create -V 1gb {pool}/zvol")

        try:
            with local_s3_task({
                "path": f"/mnt/{ds}/dir1/dir2",
                "bwlimit": [{"time": "00:00", "bandwidth": 1024 * 200}],  # So it'll take 5 seconds
                "snapshot": True,
            }) as task:
                job_id = call("cloudsync.sync", task["id"])

                time.sleep(2.5)

                ps_ax = ssh("ps ax | grep rclone")

                call("core.job_wait", job_id, job=True)

                assert re.search(rf"rclone .+ /mnt/{ds}/.zfs/snapshot/cloud_sync-[0-9]+-[0-9]+/dir1/dir2", ps_ax)

            time.sleep(1)

            assert call("zfs.snapshot.query", [["dataset", "=", ds]]) == []
        finally:
            if has_zvol_sibling:
                ssh(f"zfs destroy -r {pool}/zvol")


def test_sync_onetime():
    with dataset("cloudsync_local") as local_dataset:
        with local_s3_credential() as c:
            call("cloudsync.sync_onetime", {
                "direction": "PUSH",
                "transfer_mode": "COPY",
                "path": f"/mnt/{local_dataset}",
                "credentials": c["id"],
                "attributes": {
                    "bucket": "bucket",
                    "folder": "",
                },
                "snapshot": True,
            }, job=True)


def test_abort():
    with dataset("test") as ds:
        ssh(f"dd if=/dev/urandom of=/mnt/{ds}/blob bs=1M count=1")

        with local_s3_task({
            "path": f"/mnt/{ds}",
            "bwlimit": [{"time": "00:00", "bandwidth": 1024 * 100}],  # So it'll take 10 seconds
            "snapshot": True,
        }) as task:
            job_id = call("cloudsync.sync", task["id"])

            time.sleep(2.5)

            call("core.job_abort", job_id)

            time.sleep(1)

            assert "rclone" not in ssh("ps ax")
            assert call("cloudsync.query", [["id", "=", task["id"]]], {"get": True})["job"]["state"] == "ABORTED"

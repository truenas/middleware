import re
import time

import pytest
from pytest_dependency import depends
from middlewared.test.integration.assets.cloud_sync import credential, task, local_s3_credential, local_s3_task, run_task
from middlewared.test.integration.assets.ftp import anonymous_ftp_server, ftp_server_with_user_account
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, pool, ssh

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import dev_test, ha
reason = 'Skipping for test development testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)


def test_include(request):
    depends(request, ["pool_04"], scope="session")
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


def test_exclude_recycle_bin(request):
    depends(request, ["pool_04"], scope="session")
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
def test_ftp_subfolder(request, anonymous, defaultroot, has_leading_slash):
    depends(request, ["pool_04"], scope="session")
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
def test_snapshot(request, has_zvol_sibling):
    depends(request, ["pool_04"], scope="session")
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


def test_sync_onetime(request):
    depends(request, ["pool_04"], scope="session")
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
            }, job=True)


def test_abort(request):
    depends(request, ["pool_04"], scope="session")
    with dataset("test") as ds:
        ssh(f"dd if=/dev/urandom of=/mnt/{ds}/blob bs=1M count=1")

        with local_s3_task({
            "path": f"/mnt/{ds}",
            "bwlimit": [{"time": "00:00", "bandwidth": 1024 * 100}],  # So it'll take 10 seconds
        }) as task:
            job_id = call("cloudsync.sync", task["id"])

            time.sleep(2.5)

            call("core.job_abort", job_id)

            time.sleep(1)

            assert "rclone" not in ssh("ps ax")
            assert call("cloudsync.query", [["id", "=", task["id"]]], {"get": True})["job"]["state"] == "ABORTED"


@pytest.mark.flaky(reruns=5, reruns_delay=5)
@pytest.mark.parametrize("create_empty_src_dirs", [True, False])
def test_create_empty_src_dirs(request, create_empty_src_dirs):
    depends(request, ["pool_04"], scope="session")
    with dataset("cloudsync_local") as local_dataset:
        ssh(f"mkdir /mnt/{local_dataset}/empty-dir")
        ssh(f"mkdir /mnt/{local_dataset}/non-empty-dir")
        ssh(f"touch /mnt/{local_dataset}/non-empty-dir/file")

        with anonymous_ftp_server() as ftp:
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
                with task({
                    "direction": "PUSH",
                    "transfer_mode": "SYNC",
                    "path": f"/mnt/{local_dataset}",
                    "credentials": c["id"],
                    "attributes": {
                        "folder": "",
                    },
                    "create_empty_src_dirs": create_empty_src_dirs,
                }) as t:
                    run_task(t)

                    if create_empty_src_dirs:
                        assert ssh(f'ls /mnt/{ftp.dataset}') == 'empty-dir\nnon-empty-dir\n'
                    else:
                        assert ssh(f'ls /mnt/{ftp.dataset}') == 'non-empty-dir\n'


def test_state_persist():
    with dataset("test") as ds:
        with local_s3_task({
            "path": f"/mnt/{ds}",
        }) as task:
            call("cloudsync.sync", task["id"], job=True)

            row = call("datastore.query", "tasks.cloudsync", [["id", "=", task["id"]]], {"get": True})
            assert row["job"]["state"] == "SUCCESS"


if ha:
    def test_state_failover():
        with dataset("test") as ds:
            with local_s3_task({
                "path": f"/mnt/{ds}",
            }) as task:
                call("cloudsync.sync", task["id"], job=True)

                time.sleep(5)  # Job sending is not synchronous, allow it to propagate

                local_job = call("cloudsync.get_instance", task["id"])["job"]
                local_logs_path = local_job["logs_path"]
                local_logs = call("filesystem.file_get_contents", local_logs_path)

                remote_job = call("failover.call_remote", "cloudsync.get_instance", [task["id"]])["job"]
                remote_logs_path = remote_job["logs_path"]
                remote_logs = call("failover.call_remote", "filesystem.file_get_contents", [remote_logs_path])

                assert local_logs == remote_logs

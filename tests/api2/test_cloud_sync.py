import re
import time

import pytest
from middlewared.test.integration.assets.cloud_sync import credential, task, local_ftp_credential
from middlewared.test.integration.assets.cloud_sync import local_ftp_task, run_task
from middlewared.test.integration.assets.ftp import anonymous_ftp_server, ftp_server_with_user_account
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, pool, ssh

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import ha
pytestmark = pytest.mark.cloudsync


def test_include(request):
    with local_ftp_task({
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

        assert ssh(f'ls /mnt/{pool}/cloudsync_remote') == 'office\nwork\n'


def test_exclude_recycle_bin(request):
    with local_ftp_task({
        "exclude": ["$RECYCLE.BIN/"],
    }) as task:
        ssh(f'mkdir {task["path"]}/\'$RECYCLE.BIN\'')
        ssh(f'touch {task["path"]}/\'$RECYCLE.BIN\'/garbage')
        ssh(f'touch {task["path"]}/file')

        run_task(task)

        assert ssh(f'ls /mnt/{pool}/cloudsync_remote') == 'file\n'


@pytest.mark.flaky(reruns=5, reruns_delay=5)
@pytest.mark.parametrize("anonymous", [True, False])
@pytest.mark.parametrize("defaultroot", [True, False])
@pytest.mark.parametrize("has_leading_slash", [True, False])
def test_ftp_subfolder(request, anonymous, defaultroot, has_leading_slash):
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
    with dataset("test_cloudsync_snapshot") as ds:
        ssh(f"mkdir -p /mnt/{ds}/dir1/dir2")
        ssh(f"dd if=/dev/urandom of=/mnt/{ds}/dir1/dir2/blob bs=1M count=1")

        if has_zvol_sibling:
            ssh(f"zfs create -V 1gb {pool}/zvol")

        try:
            with local_ftp_task({
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
    with dataset("cloudsync_local") as local_dataset:
        with local_ftp_credential() as c:
            call("cloudsync.sync_onetime", {
                "direction": "PUSH",
                "transfer_mode": "COPY",
                "path": f"/mnt/{local_dataset}",
                "credentials": c["id"],
                "attributes": {
                    "folder": "",
                },
            }, job=True)


def test_abort(request):
    with dataset("test_cloudsync_abort") as ds:
        ssh(f"dd if=/dev/urandom of=/mnt/{ds}/blob bs=1M count=1")

        with local_ftp_task({
            "path": f"/mnt/{ds}",
            "bwlimit": [{"time": "00:00", "bandwidth": 1024 * 100}],  # So it'll take 10 seconds
        }) as task:
            job_id = call("cloudsync.sync", task["id"])

            time.sleep(2.5)

            call("core.job_abort", job_id)

            for i in range(10):
                time.sleep(1)
                state = call("cloudsync.query", [["id", "=", task["id"]]], {"get": True})["job"]["state"]
                if state == "RUNNING":
                    continue
                elif state == "ABORTED":
                    break
                else:
                    assert False, f"Cloud sync task is {state}"
            else:
                assert False, "Cloud sync task was not aborted"

            assert "rclone" not in ssh("ps ax")


@pytest.mark.flaky(reruns=5, reruns_delay=5)
@pytest.mark.parametrize("create_empty_src_dirs", [True, False])
def test_create_empty_src_dirs(request, create_empty_src_dirs):
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
    with dataset("test_cloudsync_state_persist") as ds:
        with local_ftp_task({
            "path": f"/mnt/{ds}",
        }) as task:
            call("cloudsync.sync", task["id"], job=True)

            row = call("datastore.query", "tasks.cloudsync", [["id", "=", task["id"]]], {"get": True})
            assert row["job"]["state"] == "SUCCESS"


if ha:
    def get_controllers_ips():
        return os.environ.get('controller1_ip'), os.environ.get('controller2_ip')

    def test_state_failover():
        assert call("failover.status") == "MASTER"

        with dataset("test_cloudsync_state_failover") as ds:
            with local_ftp_task({"path": f"/mnt/{ds}"}) as task:
                call("cloudsync.sync", task["id"], job=True)
                time.sleep(5)  # Job sending is not synchronous, allow it to propagate

                ctrl1_ip, ctrl2_ip = get_controllers_ips()
                assert all((ctrl1_ip, ctrl2_ip)), 'Unable to determine both HA controller IP addresses'

                file1_path = call("cloudsync.get_instance", task["id"])["job"]["logs_path"]
                file1_contents = ssh(f'cat {file1_path}', ip=ctrl1_ip)
                assert file1_contents

                file2_path = call("failover.call_remote", "cloudsync.get_instance", [task["id"]])["job"]["logs_path"]
                file2_contents = ssh(f'cat {file2_path}', ip=ctrl2_ip)
                assert file2_contents

                assert file1_contents == file2_contents

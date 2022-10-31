import pytest
from pytest_dependency import depends

from middlewared.test.integration.assets.keychain import localhost_ssh_credentials
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.replication import task
from middlewared.test.integration.utils import call, pool, ssh

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import dev_test
reason = 'Skipping for test development testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)


@pytest.fixture(scope="module")
def ssh_credentials():
    with localhost_ssh_credentials(username="root") as c:
        yield c


@pytest.mark.parametrize("data,path,include", [
    ({"direction": "PUSH", "source_datasets": ["data/child"]}, "/mnt/data/", True),
    ({"direction": "PUSH", "source_datasets": ["data/child"]}, "/mnt/data/child", True),
    ({"direction": "PUSH", "source_datasets": ["data/child"]}, "/mnt/data/child/work", False),
    ({"direction": "PULL", "target_dataset": "data/child"}, "/mnt/data", True),
    ({"direction": "PULL", "target_dataset": "data/child"}, "/mnt/data/child", True),
    ({"direction": "PULL", "target_dataset": "data/child"}, "/mnt/data/child/work", False),
])
def test_query_attachment_delegate(ssh_credentials, data, path, include):
    data = {
        "name": "Test",
        "transport": "SSH",
        "source_datasets": ["source"],
        "target_dataset": "target",
        "recursive": False,
        "name_regex": ".+",
        "auto": False,
        "retention_policy": "NONE",
        **data,
    }
    if data["transport"] == "SSH":
        data["ssh_credentials"] = ssh_credentials["credentials"]["id"]

    with task(data) as t:
        result = call("pool.dataset.query_attachment_delegate", "replication", path, True)
        if include:
            assert len(result) == 1
            assert result[0]["id"] == t["id"]
        else:
            assert len(result) == 0


@pytest.mark.parametrize("exclude_mountpoint_property", [True, False])
def test_run_onetime__exclude_mountpoint_property(request, exclude_mountpoint_property):
    depends(request, ["pool_04"], scope="session")
    with dataset("src") as src:
        with dataset("src/legacy") as src_legacy:
            ssh(f"zfs set mountpoint=legacy {src_legacy}")
            ssh(f"zfs snapshot -r {src}@2022-01-01-00-00-00")

            try:
                call("replication.run_onetime", {
                    "direction": "PUSH",
                    "transport": "LOCAL",
                    "source_datasets": [src],
                    "target_dataset": f"{pool}/dst",
                    "recursive": True,
                    "also_include_naming_schema": ["%Y-%m-%d-%H-%M-%S"],
                    "retention_policy": "NONE",
                    "replicate": True,
                    "readonly": "IGNORE",
                    "exclude_mountpoint_property": exclude_mountpoint_property
                }, job=True)

                mountpoint = ssh(f"zfs get -H -o value mountpoint {pool}/dst/legacy").strip()
                if exclude_mountpoint_property:
                    assert mountpoint == f"/mnt/{pool}/dst/legacy"
                else:
                    assert mountpoint == "legacy"
            finally:
                ssh(f"zfs destroy -r {pool}/dst", check=False)

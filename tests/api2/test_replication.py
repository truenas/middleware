import contextlib
import time

import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, pool, ssh

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import dev_test
reason = 'Skip for testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)


@pytest.mark.parametrize("exclude_mountpoint_property", [True, False])
def test_run_onetime__exclude_mountpoint_property(exclude_mountpoint_property):
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

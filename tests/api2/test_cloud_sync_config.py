import time

import pytest
from pytest_dependency import depends
from middlewared.test.integration.assets.cloud_sync import credential, task
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.mock_rclone import mock_rclone

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import dev_test
reason = 'Skipping for test development testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)


def test_rclone_config_writer_bool(request):
    #depends(request, ["pool_04"], scope="session")
    with dataset("test") as ds:
        with credential({
            "name": "Google Cloud Storage",
            "provider": "GOOGLE_CLOUD_STORAGE",
            "attributes": {
                "service_account_credentials": "{\"project_id\": 1}",
            },
        }) as c:
            with task({
                "direction": "PUSH",
                "transfer_mode": "COPY",
                "path": f"/mnt/{ds}",
                "credentials": c["id"],
                "attributes": {
                    "bucket": "bucket",
                    "folder": "",
                    "bucket_policy_only": True,
                },
            }) as t:
                with mock_rclone() as mr:
                    call("cloudsync.sync", t["id"])

                    time.sleep(2.5)

                    assert mr.result["config"]["remote"]["bucket_policy_only"] == "true"

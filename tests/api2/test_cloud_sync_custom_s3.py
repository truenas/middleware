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
pytestmark = pytest.mark.cloudsync


@pytest.mark.parametrize("credential_attributes,result", [
    (
        {

            "endpoint": "s3.fr-par.scw.cloud",
            "region": "fr-par",
            "skip_region": False,
            "signatures_v2": False,
        },
        {"region": "fr-par"},
    )
])
def test_custom_s3(request, credential_attributes, result):
    with dataset("test_cloudsync_custom_s3") as ds:
        with credential({
            "name": "S3",
            "provider": "S3",
            "attributes": {
                "access_key_id": "test",
                "secret_access_key": "test",
                **credential_attributes,
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
                },
            }) as t:
                with mock_rclone() as mr:
                    call("cloudsync.sync", t["id"])

                    time.sleep(2.5)

                    assert mr.result["config"]["remote"]["region"] == "fr-par"

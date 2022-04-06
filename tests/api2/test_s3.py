import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.s3 import s3_server
from middlewared.test.integration.utils import call, ssh
from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import dev_test
reason = 'Skip for testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)


def test_s3_attachment_delegate__works():
    with dataset("test") as test_dataset:
        ssh(f"mkdir /mnt/{test_dataset}/s3_root")

        with s3_server(f"{test_dataset}/s3_root"):
            assert call("pool.dataset.attachments", test_dataset) == [{
                "type": "S3", "service": "s3", "attachments": [test_dataset]
            }]

            call("pool.dataset.delete", test_dataset)

            assert not call("service.started", "s3")


def test_s3_attachment_delegate__works_for_poor_s3_configuration():
    with dataset("test") as test_dataset:
        old_path = "/mnt/unavailable-pool/s3"
        ssh(f"mkdir -p {old_path}")
        try:
            call("datastore.update", "services.s3", 1, {"s3_disks": old_path})
            assert call("pool.dataset.attachments", test_dataset) == []
        finally:
            ssh(f"rm -rf {old_path}")

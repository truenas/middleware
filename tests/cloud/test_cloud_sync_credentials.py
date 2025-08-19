from middlewared.test.integration.assets.cloud_sync import local_ftp_credential_data
from middlewared.test.integration.utils import call


def test_verify_cloud_credential():
    with local_ftp_credential_data() as data:
        assert call("cloudsync.credentials.verify", data["provider"])["valid"]


def test_verify_cloud_credential_fail():
    with local_ftp_credential_data() as data:
        data["provider"]["user"] = "root"
        assert not call("cloudsync.credentials.verify", data["provider"])["valid"]

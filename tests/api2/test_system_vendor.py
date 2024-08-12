from middlewared.test.integration.utils import call, ssh


SENTINEL_FILE_PATH = "/data/.vendor"


def test_no_vendor_file():
    file_exists = ssh(f"test -e {SENTINEL_FILE_PATH}", check=False, complete_response=True)["result"]
    assert not file_exists
    assert not call("system.vendor.is_vendored")


def test_name_is_none():
    vendor_name = call("system.vendor.name")
    assert vendor_name is None

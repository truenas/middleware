from middlewared.test.integration.utils import call, ssh


SENTINEL_FILE_PATH = "/data/.vendor"


def test_name_is_none():
    # /data/.vendor should not exist
    output = ssh(f"test -e {SENTINEL_FILE_PATH} && echo {SENTINEL_FILE_PATH}", check=False)
    assert SENTINEL_FILE_PATH not in output

    # system.vendor.name should successfully return None
    vendor_name = call("system.vendor.name")
    assert vendor_name is None

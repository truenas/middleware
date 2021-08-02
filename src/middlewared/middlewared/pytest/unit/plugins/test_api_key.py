import pytest

from middlewared.plugins.api_key import ApiKey


@pytest.mark.parametrize("allowed_resource,resource,result", [
    ("system.info", "system.info", True),
    ("system.info", "system.information", False),
    ("system.information", "system.info", False),
    ("system.*", "system.info", True),
    ("system.*", "disk.info", False),
    ("disk.*_info", "disk.info", False),
    ("disk.*_info", "disk.ssd_info", True),
    ("disk.*_info", "disk.ssd_information", False),
])
def test__api_key__authorize(allowed_resource, resource, result):
    method = "METHOD"
    api_key = ApiKey({"allowlist": [{"method": method, "resource": allowed_resource}]})
    assert api_key.authorize(method, resource) == result

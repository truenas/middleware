import pytest
from pytest_dependency import depends
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.pool import dataset

import os
import sys
sys.path.append(os.getcwd())

pytestmark = pytest.mark.zfs


@pytest.mark.parametrize("id", ["0", "root"])
@pytest.mark.parametrize("quota_type,error", [
    (["USER", "user quota on uid"]),
    (["USEROBJ", "userobj quota on uid"]),
    (["GROUP", "group quota on gid"]),
    (["GROUPOBJ", "groupobj quota on gid"]),
])
def test_errors(request, id, quota_type, error):
    with dataset("test_pool_dataset_setquota") as ds:
        with pytest.raises(ValidationErrors) as ve:
            call("pool.dataset.set_quota", ds, [{"quota_type": quota_type, "id": id, "quota_value": 5242880}])

        assert ve.value.errors[0].errmsg == f"Setting {error} [0] is not permitted"

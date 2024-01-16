import os
import pytest

from middlewared.client.client import ValidationErrors
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, ssh


def test_kubernetes_pool_of_smb_share_validation_error():
    with another_pool() as tmp_pool:
        with smb_share(os.path.join('/mnt', tmp_pool['name']), 'smbtest_share'):
            with pytest.raises(ValidationErrors) as ve:
                call('kubernetes.update', {'pool': pool_name}, job=True)

            assert ve.value.errors[0].errmsg == ('This pool cannot be used as the root dataset is used '
                                                 'by \'cifs\' service')
            assert ve.value.errors[0].attribute == 'kubernetes_update.pool'

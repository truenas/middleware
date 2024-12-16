import errno

import pytest

from middlewared.test.integration.utils import call


def test_root_zlogin_doesnt_exist():
    with pytest.raises(Exception) as ce:
        call("filesystem.stat", "/root/.zlogin")
    assert ce.value.errno == errno.ENOENT

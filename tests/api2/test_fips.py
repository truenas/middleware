import os
import pytest
import sys

from middlewared.test.integration.utils import call


sys.path.append(os.getcwd())


@pytest.mark.parametrize("flag", [
    True,
    False,
])
def test_fips(flag):
    call('system.security.update', {'enable_fips': flag})
    assert call('system.security.fips_enabled') is flag

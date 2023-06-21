import pytest

from middlewared.test.integration.utils import call


@pytest.mark.parametrize('flag', [
    True,
    False,
    True,  # Doing it again just to ensure system is still consistent
    False,
])
def test_fips(flag):
    call('system.security.update', {'enable_fips': flag})
    assert call('system.security.fips_enabled') is flag

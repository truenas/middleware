import pytest
from truenas_api_client import Client, ClientException

@pytest.fixture(scope='function')
def enable_stig():
    with Client() as c:
        c.call('datastore.update', 'system.security', 1, {'enable_gpos_stig': True})
        try:
            yield c
        finally:
            c.call('datastore.update', 'system.security', 1, {'enable_gpos_stig': False})


def test__stig_restrictions_af_unix(enable_stig):
    # STIG RBAC should still be effective despite root session
    with pytest.raises(ClientException, match='Not authorized'):
        with Client() as c:
            c.call('docker.update', {}, job=True)

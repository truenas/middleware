import errno
import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import call


@pytest.mark.parametrize('role,endpoint,valid_role', (
    ('READONLY_ADMIN', 'webui.crypto.certificate_profiles', True),
    ('READONLY_ADMIN', 'webui.crypto.certificateauthority_profiles', True),
    ('NETWORK_INTERFACE_WRITE', 'webui.crypto.certificate_profiles', False),
    ('NETWORK_INTERFACE_WRITE', 'webui.crypto.certificateauthority_profiles', False),
))
def test_ui_crypto_profiles_readonly_role(role, endpoint, valid_role):
    with unprivileged_user_client(roles=[role]) as c:
        if valid_role:
            c.call(endpoint)
        else:
            with pytest.raises(CallError) as ve:
                c.call(endpoint)

            assert ve.value.errno == errno.EACCES
            assert ve.value.errmsg == 'Not authorized'


@pytest.mark.parametrize('role,valid_role', (
    ('READONLY_ADMIN', True),
    ('NETWORK_INTERFACE_WRITE', False),
))
def test_ui_crypto_domain_names_readonly_role(role, valid_role):
    default_certificate = call('certificate.query', [('name', '=', 'truenas_default')])
    if not default_certificate:
        pytest.skip('Default certificate does not exist which is required for this test')
    else:
        default_certificate = default_certificate[0]

    with unprivileged_user_client(roles=[role]) as c:
        if valid_role:
            c.call('webui.crypto.get_certificate_domain_names', default_certificate['id'])
        else:
            with pytest.raises(CallError) as ve:
                c.call('webui.crypto.get_certificate_domain_names', default_certificate['id'])

            assert ve.value.errno == errno.EACCES
            assert ve.value.errmsg == 'Not authorized'

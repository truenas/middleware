import pytest

from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.product import product_type, set_fips_available
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.smb import smb_connection
from samba import ntstatus, NTSTATUSError

OLD_DATE = 1711547527


@pytest.fixture(scope='function')
def share():
    with dataset('null_dacl_test', {'share_type': 'SMB'}) as ds:
        with smb_share(f'/mnt/{ds}', 'DACL_TEST_SHARE') as s:
            yield {'ds': ds, 'share': s}


@pytest.fixture(scope='function')
def old_user(unprivileged_user_fixture):
    user_id = call('user.query', [['username', '=', unprivileged_user_fixture.username]], {'get': True})['id']
    call('datastore.update', 'account.bsdusers', user_id, {'bsdusr_last_password_change': OLD_DATE})
    call('etc.generate', 'shadow')
    user = call('user.get_instance', user_id)
    yield user | {'password': unprivileged_user_fixture.password}


@pytest.fixture(scope='function')
def enterprise_product():
    with product_type('ENTERPRISE'):
        with set_fips_available(True):
            yield


@pytest.fixture(scope='function')
def set_max_password_age(enterprise_product):
    call('system.security.update', {'max_password_age': 60}, job=True)
    try:
        yield
    finally:
        call('system.security.update', {'max_password_age': None}, job=True)


def test_account_expired(old_user, share, set_max_password_age):
    call('smb.synchronize_passdb', job=True)
    passdb = call('smb.passdb_list')

    assert passdb[0]['username'] == old_user['username'], str(passdb)
    assert passdb[0]['times']['pass_last_set'] == OLD_DATE, str(passdb)

    # local account with expired password due to aging should fail
    with pytest.raises(NTSTATUSError) as nt_err:
        with smb_connection(
            share=share['share']['name'],
            username=old_user['username'],
            password=old_user['password']
        ):
            pass

    assert nt_err.value.args[0] == ntstatus.NT_STATUS_PASSWORD_EXPIRED

    call('user.set_password', {'username': old_user['username'], 'new_password': old_user['password']})

    # resetting password (even if identical to old one) should allow to succeed
    with smb_connection(
        share=share['share']['name'],
        username=old_user['username'],
        password=old_user['password']
    ):
        pass

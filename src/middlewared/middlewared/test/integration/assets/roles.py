import collections
import contextlib
import errno
import random
import pytest
import string

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.account import unprivileged_user
from middlewared.test.integration.utils import call, client


USER_FIXTURE_TUPLE = collections.namedtuple('UserFixture', 'username password group_name')


@pytest.fixture(scope='module')
def unprivileged_user_fixture(request):
    suffix = ''.join([random.choice(string.ascii_lowercase + string.digits) for _ in range(8)])
    group_name = f'unprivileged_users_fixture_{suffix}'
    with unprivileged_user(
        username=f'unprivileged_fixture_{suffix}',
        group_name=group_name,
        privilege_name=f'Unprivileged users fixture ({suffix})',
        allowlist=[],
        roles=[],
        web_shell=False,
    ) as t:
        yield USER_FIXTURE_TUPLE(t.username, t.password, group_name)


@contextlib.contextmanager
def unprivileged_custom_user_client(user_client_context):
    with client(auth=(user_client_context.username, user_client_context.password)) as c:
        c.username = user_client_context.username
        yield c


def common_checks(
    user_client_context, method, role, valid_role, valid_role_exception=True, method_args=None,
    method_kwargs=None, is_return_type_none=False,
):
    method_args = method_args or []
    method_kwargs = method_kwargs or {}
    privilege = call('privilege.query', [['local_groups.0.group', '=', user_client_context.group_name]])
    assert len(privilege) > 0, 'Privilege not found'

    call('privilege.update', privilege[0]['id'], {'roles': [role]})

    with unprivileged_custom_user_client(user_client_context) as client:
        if valid_role:
            if valid_role_exception:
                with pytest.raises(Exception) as exc_info:
                    client.call(method, *method_args, **method_kwargs)

                assert not (
                    isinstance(exc_info.value, CallError) and
                    exc_info.value.errno == errno.EACCES and
                    exc_info.value.errmsg == 'Not authorized'
                )

            elif is_return_type_none:
                assert client.call(method, *method_args, **method_kwargs) is None
            else:
                assert client.call(method, *method_args, **method_kwargs) is not None
        else:
            with pytest.raises(CallError) as ve:
                client.call(method, *method_args, **method_kwargs)
            assert ve.value.errno == errno.EACCES
            assert ve.value.errmsg == 'Not authorized'

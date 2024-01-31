import errno
import pytest

from middlewared.client.client import ClientException
from middlewared.test.integration.assets.account import unprivileged_user_client


def common_checks(
    method, role, valid_role, valid_role_exception=True, method_args=None, method_kwargs=None, is_return_type_none=False
):
    method_args = method_args or []
    method_kwargs = method_kwargs or {}
    with unprivileged_user_client(roles=[role]) as client:
        if valid_role:
            if valid_role_exception:
                with pytest.raises(Exception) as exc_info:
                    client.call(method, *method_args, **method_kwargs)

                assert not isinstance(exc_info.value, ClientException)

            elif is_return_type_none:
                assert client.call(method, *method_args, **method_kwargs) is None
            else:
                assert client.call(method, *method_args, **method_kwargs) is not None
        else:
            with pytest.raises(ClientException) as ve:
                client.call(method, *method_args, **method_kwargs)
            assert ve.value.errno == errno.EACCES
            assert ve.value.error == 'Not authorized'

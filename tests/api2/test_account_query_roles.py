import pytest

from middlewared.test.integration.assets.account import unprivileged_user_client


@pytest.mark.parametrize("role", ["READONLY_ADMIN", "FULL_ADMIN"])
def test_user_role_in_account(role):
    with unprivileged_user_client(roles=[role]) as c:
        this_user = c.call("user.query", [["username", "=", c.username]], {"get": True})

        assert this_user['roles'] == [role]

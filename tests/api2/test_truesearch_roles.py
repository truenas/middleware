import pytest

from middlewared.test.integration.assets.roles import common_checks


# truesearch.query can search as another user, and its results can show more than file attributes. Thus, the
# minimum role is READONLY_ADMIN. SHARING_ADMIN and FULL_ADMIN include it.
@pytest.mark.parametrize(
    "role,should_work",
    [
        ("FILESYSTEM_ATTRS_READ", False),
        ("FILESYSTEM_DATA_READ", False),
        ("READONLY_ADMIN", True),
        ("SHARING_ADMIN", True),
    ],
)
def test_truesearch_query_role(unprivileged_user_fixture, role, should_work):
    # The path is not indexed, so a permitted call fails for that reason and not for the role.
    common_checks(
        unprivileged_user_fixture,
        "truesearch.query",
        role,
        should_work,
        valid_role_exception=True,
        method_args=[{"path": "/mnt/truesearch_roles_not_indexed"}],
    )

from unittest.mock import AsyncMock, Mock

import pytest

from middlewared.plugins.account_.privilege import PrivilegeService
from middlewared.plugins.system_general.update import SystemGeneralService
from middlewared.pytest.unit.middleware import Middleware


def user(id_, username, *, locked=False, password_disabled=False):
    return {
        "id": id_,
        "username": username,
        "unixhash": "$6$hash",
        "locked": locked,
        "password_disabled": password_disabled,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "root,group_admins,effective",
    [
        (user(0, "root", locked=True), [], True),
        (user(0, "root", password_disabled=True), [], True),
        (user(0, "root"), [], False),
        (user(0, "root", locked=True), [user(1000, "truenas_admin")], False),
    ],
)
async def test_unentitled_ds_auth_stays_on_without_a_usable_local_admin(root, group_admins, effective):
    """A revoke must not lock out a box whose only local administrator is a root that cannot log in,
    and that root must still count for `privilege.local_administrators` (it guards the unauthenticated
    first-admin setup)."""
    m = Middleware()
    m["user.query"] = AsyncMock(return_value=[root, *group_admins])
    m["group.query"] = AsyncMock(return_value=[])
    m["datastore.query"] = AsyncMock(return_value={"local_groups": [544]})
    m["group.get_password_enabled_users"] = AsyncMock(return_value=group_admins)
    m["privilege.local_administrators"] = PrivilegeService(m).local_administrators
    m.services.truenas.entitlements.check = Mock(return_value=Mock(entitled=False))

    service = SystemGeneralService(m)
    service.config = AsyncMock(return_value={"ds_auth": True})

    assert await m.call("privilege.local_administrators") == (group_admins or [root])
    assert await service.ds_auth_effective() is effective

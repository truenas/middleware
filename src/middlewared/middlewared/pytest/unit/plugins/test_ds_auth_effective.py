from unittest.mock import AsyncMock, Mock

import pytest

from middlewared.plugins.system_general.update import SystemGeneralService
from middlewared.pytest.unit.middleware import Middleware


def user(id_, username, *, locked=False):
    return {"id": id_, "username": username, "locked": locked, "password_disabled": False}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "local_admins,effective",
    [
        ([user(0, "root", locked=True)], True),
        ([user(0, "root")], False),
        ([user(1000, "truenas_admin")], False),
    ],
)
async def test_unentitled_ds_auth_stays_on_without_a_usable_local_admin(local_admins, effective):
    """A revoke must not lock out a box whose only local administrator is a root that cannot log in."""
    m = Middleware()
    m["privilege.local_administrators"] = AsyncMock(return_value=local_admins)
    m.services.truenas.entitlements.check = Mock(return_value=Mock(entitled=False))

    service = SystemGeneralService(m)
    service.config = AsyncMock(return_value={"ds_auth": True})

    assert await service.ds_auth_effective() is effective

import pytest

from middlewared.plugins.pool_.export import PoolService
from middlewared.pytest.unit.middleware import Middleware


class Delegate:
    name = "test"

    def __init__(self, raises=False):
        self.destroyed = []
        self.raises = raises

    async def destroy(self, path):
        self.destroyed.append(path)
        if self.raises:
            raise Exception("delegate blew up")


def service(delegate):
    m = Middleware()
    m["pool.dataset.get_attachment_delegates_for_stop"] = lambda *args: [delegate]
    return PoolService(m)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cascade, destroyed, expected",
    (
        # The only combination where nothing recoverable is left
        (True, True, ["/mnt/tank"]),
        # The pool was exported intact and is going somewhere else -- discarding configuration here
        # would orphan storage that is still perfectly usable
        (True, False, []),
        # `cascade=False` means the user asked to keep their attachment configuration, and the pool
        # having been destroyed does not override that
        (False, True, []),
        (False, False, []),
    ),
)
async def test_destroy_is_gated_on_cascade_and_destroyed(cascade, destroyed, expected):
    delegate = Delegate()
    await service(delegate)._destroy_pool_attachments("/mnt/tank", {"cascade": cascade, "destroy": True}, destroyed)
    assert delegate.destroyed == expected


@pytest.mark.asyncio
async def test_destroy_failure_does_not_abort_the_export():
    # The pool is already gone by this point; the rest of the export job still has to run
    delegate = Delegate(raises=True)
    await service(delegate)._destroy_pool_attachments("/mnt/tank", {"cascade": True, "destroy": True}, True)
    assert delegate.destroyed == ["/mnt/tank"]

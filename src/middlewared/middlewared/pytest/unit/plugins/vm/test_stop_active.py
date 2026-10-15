from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from middlewared.plugins.vm import lifecycle
from middlewared.pytest.unit.middleware import FakeJob


@pytest.mark.asyncio
async def test_stop_active_powers_off_suspended_vm():
    """A graceful stop leaves a suspended guest running."""
    vms = [
        SimpleNamespace(id=1, name="vm1", status=SimpleNamespace(state="RUNNING")),
        SimpleNamespace(id=2, name="vm2", status=SimpleNamespace(state="SUSPENDED")),
    ]
    stopped = []

    def stop(id_, options):
        stopped.append(id_)
        return FakeJob()

    context = Mock()
    handlers = {context.s.vm.query: lambda *args: vms, context.s.vm.stop: stop}

    async def call2(f, *args):
        return handlers[f](*args)

    async def to_thread(f, *args):
        return f(*args)

    context.call2 = call2
    context.to_thread = to_thread

    with patch.object(lifecycle, "poweroff_vm") as poweroff:
        await lifecycle.stop_active(context)

    assert stopped == [1]
    assert [c.args[1] for c in poweroff.call_args_list] == [2]

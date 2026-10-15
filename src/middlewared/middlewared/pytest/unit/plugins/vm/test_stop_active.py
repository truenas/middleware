from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from middlewared.plugins.vm import lifecycle
from middlewared.pytest.unit.middleware import FakeJob
from middlewared.service_exception import CallError


def make_context(states, resumable):
    vms = {
        id_: SimpleNamespace(id=id_, name=f"vm{id_}", status=SimpleNamespace(state=state))
        for id_, state in states.items()
    }
    stopped = []

    def resume(id_):
        if id_ not in resumable:
            raise RuntimeError("resume failed")
        vms[id_].status.state = "RUNNING"

    def stop(id_, options):
        stopped.append(id_)
        return FakeJob()

    context = Mock()
    vm = context.s.vm
    handlers = {
        vm.query: lambda *args: list(vms.values()),
        vm.get_instance: lambda id_: vms[id_],
        vm.resume: resume,
        vm.stop: stop,
    }

    async def call2(f, *args):
        return handlers[f](*args)

    async def to_thread(f, *args):
        return f(*args)

    context.call2 = call2
    context.to_thread = to_thread
    return context, stopped


@pytest.mark.asyncio
async def test_stop_active_resumes_suspended_vm_and_powers_off_one_that_will_not_resume():
    """A suspended VM left running after a revoke or shutdown because it was never resumed or would not resume."""
    context, stopped = make_context({1: "RUNNING", 2: "SUSPENDED", 3: "SUSPENDED"}, resumable={2})

    with patch.object(lifecycle, "poweroff_vm") as poweroff:
        await lifecycle.stop_active(context)

    assert sorted(stopped) == [1, 2]
    assert [c.args[1] for c in poweroff.call_args_list] == [3]


@pytest.mark.asyncio
async def test_stop_active_raises_when_libvirt_is_unreachable():
    """An unreachable libvirt must not pass for a completed revoke."""
    context, stopped = make_context({1: "STOPPED"}, resumable=set())
    context.middleware.libvirt_domains_manager.vms_connection.list_domains.side_effect = RuntimeError("no socket")

    with pytest.raises(CallError, match="libvirt is unreachable"):
        await lifecycle.stop_active(context)

    assert stopped == []

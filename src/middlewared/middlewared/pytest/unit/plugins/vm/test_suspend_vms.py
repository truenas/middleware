from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from middlewared.plugins.vm import lifecycle


def make_vm(id_, name, state, suspend_on_snapshot):
    return SimpleNamespace(
        id=id_,
        name=name,
        status=SimpleNamespace(state=state),
        suspend_on_snapshot=suspend_on_snapshot,
    )


def make_context(vms):
    context = Mock()
    context.call_sync2 = Mock(return_value=vms)
    context.logger = Mock()
    return context


@pytest.mark.parametrize(
    "vms,expected_suspended",
    [
        # Running and opted in -> suspended.
        ([make_vm(1, "vm1", "RUNNING", True)], [1]),
        # Running but opted out -> NOT suspended (the bug being fixed).
        ([make_vm(1, "vm1", "RUNNING", False)], []),
        # Opted in but not running -> nothing to suspend.
        ([make_vm(1, "vm1", "STOPPED", True)], []),
        ([make_vm(1, "vm1", "SUSPENDED", True)], []),
        # Mixed: only the running, opted-in VM is suspended.
        (
            [
                make_vm(1, "vm1", "RUNNING", True),
                make_vm(2, "vm2", "RUNNING", False),
                make_vm(3, "vm3", "SUSPENDED", True),
                make_vm(4, "vm4", "STOPPED", True),
            ],
            [1],
        ),
    ],
)
def test_suspend_vms_only_running_opted_in(vms, expected_suspended):
    context = make_context(vms)

    with patch.object(lifecycle, "suspend_vm") as suspend_vm:
        lifecycle.suspend_vms(context, [vm.id for vm in vms])

    assert [c.args[1] for c in suspend_vm.call_args_list] == expected_suspended


def test_suspend_vms_tolerates_unknown_id():
    # An id passed in but absent from vm.query must not raise.
    context = make_context([])

    with patch.object(lifecycle, "suspend_vm") as suspend_vm:
        lifecycle.suspend_vms(context, [999])

    suspend_vm.assert_not_called()

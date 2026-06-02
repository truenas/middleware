from unittest.mock import Mock

import pytest

from middlewared.plugins.vm.vm_lifecycle import VMService


def make_service(vms):
    service = VMService.__new__(VMService)
    service.middleware = Mock()
    service.middleware.call_sync = Mock(return_value=vms)
    service.logger = Mock()
    service.suspend = Mock()
    return service


@pytest.mark.parametrize('vms,expected_suspended', [
    # Running and opted in -> suspended.
    ([{'id': 1, 'name': 'vm1', 'status': {'state': 'RUNNING'}, 'suspend_on_snapshot': True}], [1]),
    # Running but opted out -> NOT suspended (the bug being fixed).
    ([{'id': 1, 'name': 'vm1', 'status': {'state': 'RUNNING'}, 'suspend_on_snapshot': False}], []),
    # Opted in but not running -> nothing to suspend.
    ([{'id': 1, 'name': 'vm1', 'status': {'state': 'STOPPED'}, 'suspend_on_snapshot': True}], []),
    ([{'id': 1, 'name': 'vm1', 'status': {'state': 'SUSPENDED'}, 'suspend_on_snapshot': True}], []),
    # Mixed: only the running, opted-in VM is suspended.
    (
        [
            {'id': 1, 'name': 'vm1', 'status': {'state': 'RUNNING'}, 'suspend_on_snapshot': True},
            {'id': 2, 'name': 'vm2', 'status': {'state': 'RUNNING'}, 'suspend_on_snapshot': False},
            {'id': 3, 'name': 'vm3', 'status': {'state': 'SUSPENDED'}, 'suspend_on_snapshot': True},
            {'id': 4, 'name': 'vm4', 'status': {'state': 'STOPPED'}, 'suspend_on_snapshot': True},
        ],
        [1],
    ),
])
def test_suspend_vms_only_running_opted_in(vms, expected_suspended):
    service = make_service(vms)

    service.suspend_vms([vm['id'] for vm in vms])

    assert [c.args[0] for c in service.suspend.call_args_list] == expected_suspended


def test_suspend_vms_tolerates_unknown_id():
    # An id passed in but absent from vm.query must not raise.
    service = make_service([])

    service.suspend_vms([999])

    service.suspend.assert_not_called()

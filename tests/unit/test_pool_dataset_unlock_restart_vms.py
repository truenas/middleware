import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from middlewared.plugins.pool_.unlock import PoolDatasetService


def make_vm(vm_id, name, devices):
    return SimpleNamespace(
        id=vm_id,
        name=name,
        devices=[
            SimpleNamespace(attributes=SimpleNamespace(**d))
            for d in devices
        ],
    )


@pytest.fixture
def service():
    svc = PoolDatasetService.__new__(PoolDatasetService)
    svc.middleware = MagicMock()
    svc.call2 = AsyncMock()
    svc.logger = MagicMock()
    return svc


class TestUnlockRestartedVms:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("dtype,path,ds_type", [
        ("DISK", "/dev/zvol/tank/test", "VOLUME"),
        ("RAW", "/mnt/tank/test/child", "FILESYSTEM"),
    ])
    async def test_matching_device(self, service, dtype, path, ds_type):
        vm = make_vm(1, "myvm", [{"path": path, "dtype": dtype}])
        service.call2.return_value = [vm]

        dataset = {"name": "tank/test", "type": ds_type, "mountpoint": "/mnt/tank/test"}
        result = await service.unlock_restarted_vms(dataset)
        assert result == [vm]

    @pytest.mark.asyncio
    async def test_unrelated_device_no_match(self, service):
        vm = make_vm(1, "myvm", [{"path": "/dev/zvol/tank/other", "dtype": "DISK"}])
        service.call2.return_value = [vm]

        result = await service.unlock_restarted_vms({"name": "tank/test", "type": "VOLUME"})
        assert result == []

    @pytest.mark.asyncio
    async def test_non_disk_dtype_skipped(self, service):
        vm = make_vm(1, "myvm", [{"path": "/dev/zvol/tank/test", "dtype": "NIC"}])
        service.call2.return_value = [vm]

        result = await service.unlock_restarted_vms({"name": "tank/test", "type": "VOLUME"})
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_path_skipped(self, service):
        vm = make_vm(1, "myvm", [{"path": "", "dtype": "DISK"}])
        service.call2.return_value = [vm]

        result = await service.unlock_restarted_vms({"name": "tank/test", "type": "VOLUME"})
        assert result == []


class TestRestartVmsAfterUnlock:

    @pytest.mark.asyncio
    async def test_running_vm_stopped_and_started(self, service):
        vm = make_vm(1, "myvm", [{"path": "/dev/zvol/tank/test", "dtype": "DISK"}])

        stop_job = AsyncMock()
        stop_job.error = None

        s = service.s

        async def call2_side_effect(method, *args, **kwargs):
            if method == s.vm.query:
                return [vm]
            if method == s.vm.status:
                return SimpleNamespace(state="RUNNING")
            if method == s.vm.stop:
                return stop_job
            return None

        service.call2 = AsyncMock(side_effect=call2_side_effect)

        await service.restart_vms_after_unlock({"name": "tank/test", "type": "VOLUME"})

        stop_job.wait.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stopped_vm_only_started(self, service):
        vm = make_vm(1, "myvm", [{"path": "/dev/zvol/tank/test", "dtype": "DISK"}])

        s = service.s

        async def call2_side_effect(method, *args, **kwargs):
            if method == s.vm.query:
                return [vm]
            if method == s.vm.status:
                return SimpleNamespace(state="STOPPED")
            return None

        service.call2 = AsyncMock(side_effect=call2_side_effect)

        await service.restart_vms_after_unlock({"name": "tank/test", "type": "VOLUME"})

        calls = [c.args[0] for c in service.call2.call_args_list]
        assert s.vm.stop not in calls

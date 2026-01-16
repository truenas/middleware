import asyncio
import itertools
import pathlib

from middlewared.service import Service
from .utils import ISCSI_TARGET_PARAMETERS, sanitize_extent
from scstadmin import SCSTAdmin

SCST_BASE = '/sys/kernel/scst_tgt'
SCST_TARGETS_ISCSI_ENABLED_PATH = '/sys/kernel/scst_tgt/targets/iscsi/enabled'
COPY_MANAGER_LUNS_PATH = '/sys/kernel/scst_tgt/targets/copy_manager/copy_manager_tgt/luns'
SCST_DEVICES = '/sys/kernel/scst_tgt/devices'
SCST_SUSPEND = '/sys/kernel/scst_tgt/suspend'
SCST_CONTROLLER_A_TARGET_GROUPS_STATE = '/sys/kernel/scst_tgt/device_groups/targets/target_groups/controller_A/state'
SCST_CONTROLLER_B_TARGET_GROUPS_STATE = '/sys/kernel/scst_tgt/device_groups/targets/target_groups/controller_B/state'


class iSCSITargetService(Service):

    class Config:
        namespace = 'iscsi.scst'
        private = True

    def path_write(self, path, text):
        p = pathlib.Path(path)
        realpath = str(p.resolve())
        if realpath.startswith(SCST_BASE) and p.exists():
            p.write_text(text)
        else:
            raise ValueError(f'Unexpected path "{realpath}"')

    async def set_all_cluster_mode(self, value):
        text = f'{int(value)}\n'
        paths = await self.middleware.call('iscsi.scst.cluster_mode_paths')
        if paths:
            for chunk in itertools.batched(paths, 10):
                await asyncio.gather(*[self.middleware.call('iscsi.scst.path_write', path, text) for path in chunk])

    def cluster_mode_paths(self):
        scst_tgt_devices = pathlib.Path(SCST_DEVICES)
        if scst_tgt_devices.exists():
            return [str(p) for p in scst_tgt_devices.glob('*/cluster_mode')]
        else:
            return []

    def cluster_mode_devices_set(self):
        devices = []
        scst_tgt_devices = pathlib.Path(SCST_DEVICES)
        if scst_tgt_devices.exists():
            for p in scst_tgt_devices.glob('*/cluster_mode'):
                if p.read_text().splitlines()[0] == '1':
                    devices.append(p.parent.name)
        return devices

    def check_cluster_modes_clear(self):
        scst_tgt_devices = pathlib.Path(SCST_DEVICES)
        if scst_tgt_devices.exists():
            for p in scst_tgt_devices.glob('*/cluster_mode'):
                if p.read_text().splitlines()[0] == '1':
                    return False
        return True

    def check_cluster_mode_paths_present(self, devices):
        for device in devices:
            if not pathlib.Path(f'{SCST_DEVICES}/{sanitize_extent(device)}/cluster_mode').exists():
                return False
        return True

    def get_cluster_mode(self, device):
        try:
            return pathlib.Path(f'{SCST_DEVICES}/{sanitize_extent(device)}/cluster_mode').read_text().splitlines()[0]
        except Exception:
            return "UNKNOWN"

    async def set_device_cluster_mode(self, device, value):
        await self.middleware.call('iscsi.scst.path_write',
                                   f'{SCST_DEVICES}/{sanitize_extent(device)}/cluster_mode',
                                   f'{int(value)}\n')

    async def set_devices_cluster_mode(self, devices, value):
        text = f'{int(value)}\n'
        paths = [f'{SCST_DEVICES}/{sanitize_extent(device)}/cluster_mode' for device in devices]
        if paths:
            await asyncio.gather(*[self.middleware.call('iscsi.scst.path_write', path, text) for path in paths])

    def disable(self):
        pathlib.Path(SCST_TARGETS_ISCSI_ENABLED_PATH).write_text('0\n')

    def enable(self):
        pathlib.Path(SCST_TARGETS_ISCSI_ENABLED_PATH).write_text('1\n')

    def suspend(self, value=10):
        pathlib.Path(SCST_SUSPEND).write_text(f'{value}\n')

    def clear_suspend(self):
        """suspend could have been called several times, and will need to be decremented
        several times to clean"""
        try:
            p = pathlib.Path(SCST_SUSPEND)
            for i in range(30):
                if p.read_text().strip() == '0':
                    return True
                else:
                    p.write_text('-1\n')
        except FileNotFoundError:
            pass

        return False

    def enabled(self):
        try:
            return pathlib.Path(SCST_TARGETS_ISCSI_ENABLED_PATH).read_text().strip() == '1'
        except FileNotFoundError:
            return False

    def is_kernel_module_loaded(self):
        return pathlib.Path(SCST_BASE).exists()

    def activate_extent(self, extent_name, extenttype, path):
        if pathlib.Path(path).exists():
            if extenttype == 'DISK':
                p = pathlib.Path(f'{SCST_BASE}/handlers/vdisk_blockio/{sanitize_extent(extent_name)}/active')
            else:
                p = pathlib.Path(f'{SCST_BASE}/handlers/vdisk_fileio/{sanitize_extent(extent_name)}/active')
            try:
                p.write_text('1\n')
                return True
            except Exception:
                # Return False on ANY exception
                return False
        else:
            return False

    def delete_iscsi_lun(self, iqn, lun):
        pathlib.Path(f'{SCST_BASE}/targets/iscsi/{iqn}/ini_groups/security_group/luns/mgmt').write_text(f'del {lun}\n')

    def replace_iscsi_lun(self, iqn, extent, lun):
        mgmt_path = f'{SCST_BASE}/targets/iscsi/{iqn}/ini_groups/security_group/luns/mgmt'
        pathlib.Path(mgmt_path).write_text(f'replace {sanitize_extent(extent)} {lun}\n')

    def delete_fc_lun(self, wwpn, lun):
        pathlib.Path(f'{SCST_BASE}/targets/qla2x00t/{wwpn}/luns/mgmt').write_text(f'del {lun}\n')

    def replace_fc_lun(self, wwpn, extent, lun):
        mgmt_path = pathlib.Path(f'{SCST_BASE}/targets/qla2x00t/{wwpn}/luns/mgmt')
        mgmt_path.write_text(f'replace {sanitize_extent(extent)} {lun}\n')

    def set_node_optimized(self, node):
        """Update which node is reported as being the active/optimized path."""
        if node == 'A':
            pathlib.Path(SCST_CONTROLLER_B_TARGET_GROUPS_STATE).write_text("nonoptimized\n")
            pathlib.Path(SCST_CONTROLLER_A_TARGET_GROUPS_STATE).write_text("active\n")
        else:
            pathlib.Path(SCST_CONTROLLER_A_TARGET_GROUPS_STATE).write_text("nonoptimized\n")
            pathlib.Path(SCST_CONTROLLER_B_TARGET_GROUPS_STATE).write_text("active\n")

    def reset_target_parameters(self, iqn, parameter_names):
        """Reset the specified parameters to their default values."""
        # Do some sanity checking
        for param in parameter_names:
            if param not in ISCSI_TARGET_PARAMETERS:
                raise ValueError('Invalid parameter name supplied', param)
        iqndir = pathlib.Path(f'{SCST_BASE}/targets/iscsi/{iqn}')
        for param in parameter_names:
            try:
                (iqndir / pathlib.Path(param)).write_text(':default:\n')
            except (FileNotFoundError, PermissionError):
                # If we're not running, that's OK
                pass

    def apply_config_file(self):
        try:
            SCSTAdmin.apply_config_file('/etc/scst.conf')
        except Exception:
            self.logger.debug("Failed to apply SCST configuration", exc_info=True)
            return False
        return True

    def copy_manager_devices(self):
        result = []
        try:
            copy_manager_luns = pathlib.Path(COPY_MANAGER_LUNS_PATH)
            for p in copy_manager_luns.glob('*/device'):
                try:
                    result.append(p.resolve().name)
                except (FileNotFoundError, PermissionError):
                    pass
        except (FileNotFoundError, PermissionError):
            pass
        return result

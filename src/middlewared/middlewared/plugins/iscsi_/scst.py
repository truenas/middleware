import asyncio
import pathlib

from middlewared.service import Service

SCST_BASE = '/sys/kernel/scst_tgt'
SCST_TARGETS_ISCSI_ENABLED_PATH = '/sys/kernel/scst_tgt/targets/iscsi/enabled'
SCST_DEVICES = '/sys/kernel/scst_tgt/devices'
SCST_SUSPEND = '/sys/kernel/scst_tgt/suspend'


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
            await asyncio.gather(*[self.middleware.call('iscsi.scst.path_write', path, text) for path in paths])

    def cluster_mode_paths(self):
        scst_tgt_devices = pathlib.Path(SCST_DEVICES)
        if scst_tgt_devices.exists():
            return [str(p) for p in scst_tgt_devices.glob('*/cluster_mode')]
        else:
            return []

    def check_cluster_mode_paths_present(self, devices):
        for device in devices:
            if not pathlib.Path(f'{SCST_DEVICES}/{device}/cluster_mode').exists():
                return False
        return True

    async def set_devices_cluster_mode(self, devices, value):
        text = f'{int(value)}\n'
        paths = [f'{SCST_DEVICES}/{device}/cluster_mode' for device in devices]
        if paths:
            await asyncio.gather(*[self.middleware.call('iscsi.scst.path_write', path, text) for path in paths])

    def disable(self):
        p = pathlib.Path(SCST_TARGETS_ISCSI_ENABLED_PATH)
        p.write_text('0\n')

    def enable(self):
        p = pathlib.Path(SCST_TARGETS_ISCSI_ENABLED_PATH)
        p.write_text('1\n')

    def suspend(self, value):
        p = pathlib.Path(SCST_SUSPEND)
        p.write_text(f'{value}\n')

    def enabled(self):
        p = pathlib.Path(SCST_TARGETS_ISCSI_ENABLED_PATH)
        try:
            return p.read_text().strip() == '1'
        except FileNotFoundError:
            return False

    def is_kernel_module_loaded(self):
        return pathlib.Path(SCST_BASE).exists()

    def activate_extent(self, extent_name, extenttype, path):
        p = pathlib.Path(path)
        if p.exists():
            if extenttype == 'DISK':
                p = pathlib.Path(f'/sys/kernel/scst_tgt/handlers/vdisk_blockio/{extent_name}/active')
            else:
                p = pathlib.Path(f'/sys/kernel/scst_tgt/handlers/vdisk_fileio/{extent_name}/active')
            p.write_text('1\n')
            return True
        else:
            return False

    def activate_extents(self, extents):
        for extent in extents:
            if extent['type'] == 'DISK':
                p = pathlib.Path(f'/sys/kernel/scst_tgt/handlers/vdisk_blockio/{extent["name"]}/active')
            else:
                p = pathlib.Path(f'/sys/kernel/scst_tgt/handlers/vdisk_fileio/{extent["name"]}/active')
            p.write_text('1\n')

    def replace_lun(self, iqn, extent, lun):
        p = pathlib.Path(f'/sys/kernel/scst_tgt/targets/iscsi/{iqn}/ini_groups/security_group/luns/mgmt')
        p.write_text(f'replace {extent} {lun}\n')

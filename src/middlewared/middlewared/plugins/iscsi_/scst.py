import asyncio
import itertools
import pathlib

from middlewared.service import Service
from middlewared.utils import run
from .utils import ISCSI_TARGET_PARAMETERS, sanitize_extent
from scstadmin import SCSTAdmin

SCST_BASE = '/sys/kernel/scst_tgt'
SCST_TARGETS_ISCSI_ENABLED_PATH = '/sys/kernel/scst_tgt/targets/iscsi/enabled'
COPY_MANAGER_LUNS_PATH = (
    '/sys/kernel/scst_tgt/targets/copy_manager/copy_manager_tgt/luns'
)
SCST_DEVICES = '/sys/kernel/scst_tgt/devices'
SCST_SUSPEND = '/sys/kernel/scst_tgt/suspend'
SCST_CONTROLLER_A_TARGET_GROUPS_STATE = (
    '/sys/kernel/scst_tgt/device_groups/targets/target_groups/controller_A/state'
)
SCST_CONTROLLER_B_TARGET_GROUPS_STATE = (
    '/sys/kernel/scst_tgt/device_groups/targets/target_groups/controller_B/state'
)
DISK_HANDLER_PR_DUMP_DIR_SYSFS = '/sys/kernel/scst_tgt/handlers/dev_disk/pr_dump_dir'


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
                await asyncio.gather(
                    *[
                        self.middleware.call('iscsi.scst.path_write', path, text)
                        for path in chunk
                    ]
                )

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
            if not pathlib.Path(
                f'{SCST_DEVICES}/{sanitize_extent(device)}/cluster_mode'
            ).exists():
                return False
        return True

    def get_cluster_mode(self, device):
        try:
            return (
                pathlib.Path(f'{SCST_DEVICES}/{sanitize_extent(device)}/cluster_mode')
                .read_text()
                .splitlines()[0]
            )
        except Exception:
            return 'UNKNOWN'

    async def set_device_cluster_mode(self, device, value):
        await self.middleware.call(
            'iscsi.scst.path_write',
            f'{SCST_DEVICES}/{sanitize_extent(device)}/cluster_mode',
            f'{int(value)}\n',
        )

    async def set_devices_cluster_mode(self, devices, value):
        text = f'{int(value)}\n'
        paths = [
            f'{SCST_DEVICES}/{sanitize_extent(device)}/cluster_mode'
            for device in devices
        ]
        if paths:
            await asyncio.gather(
                *[
                    self.middleware.call('iscsi.scst.path_write', path, text)
                    for path in paths
                ]
            )

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
            return (
                pathlib.Path(SCST_TARGETS_ISCSI_ENABLED_PATH).read_text().strip() == '1'
            )
        except FileNotFoundError:
            return False

    def is_kernel_module_loaded(self):
        return pathlib.Path(SCST_BASE).exists()

    def activate_extent(self, extent_name, extenttype, path):
        if pathlib.Path(path).exists():
            if extenttype == 'DISK':
                p = pathlib.Path(
                    f'{SCST_BASE}/handlers/vdisk_blockio/{sanitize_extent(extent_name)}/active'
                )
            else:
                p = pathlib.Path(
                    f'{SCST_BASE}/handlers/vdisk_fileio/{sanitize_extent(extent_name)}/active'
                )
            try:
                p.write_text('1\n')
                return True
            except Exception:
                # Return False on ANY exception
                return False
        else:
            return False

    def delete_iscsi_lun(self, iqn, lun):
        pathlib.Path(
            f'{SCST_BASE}/targets/iscsi/{iqn}/ini_groups/security_group/luns/mgmt'
        ).write_text(f'del {lun}\n')

    def replace_iscsi_lun(self, iqn, extent, lun, ua=True):
        mgmt_path = (
            f'{SCST_BASE}/targets/iscsi/{iqn}/ini_groups/security_group/luns/mgmt'
        )
        op = 'replace' if ua else 'replace_no_ua'
        pathlib.Path(mgmt_path).write_text(f'{op} {sanitize_extent(extent)} {lun}\n')

    def delete_fc_lun(self, wwpn, lun):
        pathlib.Path(f'{SCST_BASE}/targets/qla2x00t/{wwpn}/luns/mgmt').write_text(
            f'del {lun}\n'
        )

    def replace_fc_lun(self, wwpn, extent, lun, ua=True):
        mgmt_path = pathlib.Path(f'{SCST_BASE}/targets/qla2x00t/{wwpn}/luns/mgmt')
        op = 'replace' if ua else 'replace_no_ua'
        mgmt_path.write_text(f'{op} {sanitize_extent(extent)} {lun}\n')

    def set_pr_dump_dir(self, path):
        """
        Configure the dev_disk handler to dump PR state files on device detach.

        Creates (or clears) the dump directory, then writes its path to the
        dev_disk handler sysfs attribute.  Subsequent dev_disk detaches caused
        by reset_active() will write <path>/<serial> files containing the PR
        state for each device that had cluster_mode set.

        restore_pr_state() reads those files during become_active().
        """
        dump_dir = pathlib.Path(path)
        dump_dir.mkdir(parents=True, exist_ok=True)
        for f in dump_dir.iterdir():
            f.unlink(missing_ok=True)
        try:
            pathlib.Path(DISK_HANDLER_PR_DUMP_DIR_SYSFS).write_text(f'{path}\n')
        except OSError:
            self.logger.warning('Failed to configure pr_dump_dir; '
                                'PR state will not be preserved on failover')
            return
        self._pr_dump_dir = path

    def restore_pr_state(self, extents):
        """
        Restore PR state from dump files to vdisk devices and return the set
        of extent names that were successfully restored.

        Reads <_pr_dump_dir>/<serial> files written by dev_disk on detach,
        maps serial to extent name via the extents dict, and writes the PR
        state to each vdisk's pr_state sysfs attribute.

        Called from become_active() after iSCSI is suspended but before the
        LUN swap.  become_active() uses the returned set to decide per-extent
        whether to use replace_no_ua (extent in the set) or replace-with-UA
        (extent absent — no dump file, unrecognised serial, or write failed).
        """
        pr_dump_dir = getattr(self, '_pr_dump_dir', '')
        dump_dir = pathlib.Path(pr_dump_dir) if pr_dump_dir else None
        no_ua = set()
        if not dump_dir or not dump_dir.exists():
            return no_ua

        serial_to_name = {
            ext['serial']: ext['name']
            for ext in extents.values()
            if ext.get('serial')
        }

        for dump_file in dump_dir.iterdir():
            extent_name = serial_to_name.get(dump_file.name)
            if extent_name is None:
                continue
            pr_state_path = pathlib.Path(
                f'{SCST_DEVICES}/{sanitize_extent(extent_name)}/pr_state'
            )
            try:
                pr_state_path.write_text(dump_file.read_text())
                no_ua.add(extent_name)
            except Exception:
                self.logger.warning('Failed to restore PR state for extent %r; '
                                    'will use replace (with UA) for this LUN',
                                    extent_name, exc_info=True)

        try:
            for f in dump_dir.iterdir():
                f.unlink(missing_ok=True)
        except Exception:
            self.logger.warning('Failed to clean up PR dump dir %r', str(dump_dir), exc_info=True)
        self._pr_dump_dir = ''
        return no_ua

    def set_node_optimized(self, node):
        """Update which node is reported as being the active/optimized path."""
        if node == 'A':
            pathlib.Path(SCST_CONTROLLER_B_TARGET_GROUPS_STATE).write_text(
                'nonoptimized\n'
            )
            pathlib.Path(SCST_CONTROLLER_A_TARGET_GROUPS_STATE).write_text('active\n')
        else:
            pathlib.Path(SCST_CONTROLLER_A_TARGET_GROUPS_STATE).write_text(
                'nonoptimized\n'
            )
            pathlib.Path(SCST_CONTROLLER_B_TARGET_GROUPS_STATE).write_text('active\n')

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
            self.logger.debug('Failed to apply SCST configuration', exc_info=True)
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

    async def remove_target(self, iqn: str, retries: int = 5):
        """Remove an iSCSI target from SCST via scstadmin."""
        # Retries several times with a short sleep to handle the race where
        # initiator sessions are still being torn down (NEXUS_LOSS_SESS
        # in-flight) when the call is made.
        cp = None
        for attempt in range(retries):
            cp = await run(
                [
                    'scstadmin',
                    '-force',
                    '-noprompt',
                    '-rem_target',
                    iqn,
                    '-driver',
                    'iscsi',
                ],
                check=False,
            )
            if cp.returncode == 0:
                return
            if attempt < retries - 1:
                await asyncio.sleep(1)

        # scstadmin writes errors to stdout, not stderr
        self.logger.error(
            'Failed to remove target %r after %d attempts: %s',
            iqn,
            retries,
            cp.stdout.decode() or cp.stderr.decode(),
        )

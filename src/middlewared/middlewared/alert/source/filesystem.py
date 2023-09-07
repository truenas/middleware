import os
from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.utils.osc import getmnttree


class UnexpectedMountDirContentsAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "The TrueNAS data pool mount directory contains unexpected filesystems"
    text = "The following unexpected filesystems were detected: %(err)s"


class UnexpectedMountDirContentsAlertSource(AlertSource):
    schedule = IntervalSchedule(hour=6)
    run_on_backup_node = False

    def do_tree_check(self, dev_id, k8s_dataset):
        def check_fs_type(mnt):
            if mnt['mount_source'] == k8s_dataset:
                # prune k8s dataset from tree
                return

            if mnt['fstype'] != 'zfs':
                errors.append(f'{mnt["mountpoint"]}: {mnt["fstype"]}')

            for child in mnt['children']:
                check_fs_type(child)

        errors = []
        tree = getmnttree(dev_id)
        check_fs_type(tree)
        return errors

    def check_sync(self):
        k8s_ds = self.middleware.call_sync('kubernetes.config')['dataset']
        root_dev = os.stat('/mnt/').st_dev

        errors = []
        with os.scandir('/mnt') as it:
            for entry in it:
                if entry.is_symlink():
                    errors.append(f'{entry.path}: unexpected symlink!')
                    continue

                if not entry.is_dir():
                    errors.append(f'{entry.path}: unexpected file in mount directory.')
                    continue

                try:
                    this_dev = entry.stat().st_dev
                except Exception:
                    self.middleware.logger.error(f'{entry.path}: stat() failed', exc_info=True)
                    errors.append(f'{entry.path}: failed to stat path. Review middleware log.')
                    continue

                if this_dev == root_dev:
                    # This is probably a mountpoint for pool that isn't imported
                    continue

                do_tree_check(entry.stat().st_dev, k8s_ds)

        if not errors:
            return

        return Alert(
            UnexpectedFsTypeAlertClass,
            {'err': ', '.join(errors)},
            key=None
        )

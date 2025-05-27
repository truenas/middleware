import libzfs
import subprocess

from middlewared.service import CallError, Service


class ZFSSnapshotService(Service):

    class Config:
        namespace = 'zfs.snapshot'
        process_pool = True
        private = True

    def clone(self, data):
        """
        Clone a given snapshot to a new dataset.

        Returns:
            bool: True if succeed.

        """
        snapshot = data.get('snapshot', '')
        dataset_dst = data.get('dataset_dst', '')
        props = data.get('dataset_properties', {})

        try:
            with libzfs.ZFS() as zfs:
                snp = zfs.get_snapshot(snapshot)
                snp.clone(dataset_dst, props)
                dataset = zfs.get_dataset(dataset_dst)
                if dataset.type.name == 'FILESYSTEM':
                    dataset.mount_recursive()
            self.logger.info("Cloned snapshot {0} to dataset {1}".format(snapshot, dataset_dst))
            return True
        except libzfs.ZFSException as err:
            self.logger.error("{0}".format(err))
            raise CallError(f'Failed to clone snapshot: {err}')

    def rollback(self, id_, options={}):
        """
        Rollback to a given snapshot `id`.

        `options.recursive` (bool) will destroy any snapshots and bookmarks more recent than the one
            specified.

        `options.recursive_clones` (bool) is just like `recursive` but will also destroy any clones.

        `options.force` (bool) will force unmount of any clones.

        `options.recursive_rollback` (bool) will do a complete recursive rollback of each child snapshots for `id`. If
            any child does not have specified snapshot, this operation will fail.

        """
        args = []
        if options.get('force'):
            args += ['-f']
        if options.get('recursive'):
            args += ['-r']
        if options.get('recursive_clones'):
            args += ['-R']

        if options.get('recursive_rollback'):
            dataset, snap_name = id_.rsplit('@', 1)
            datasets = set({
                f'{ds["id"]}@{snap_name}' for ds in self.middleware.call_sync(
                    'zfs.dataset.query', [['OR', [['id', '^', f'{dataset}/'], ['id', '=', dataset]]]]
                )
            })

            for snap in filter(lambda sn: self.middleware.call_sync('zfs.snapshot.query', [['id', '=', sn]]), datasets):
                self.rollback_impl(args, snap)

        else:
            self.rollback_impl(args, id_)

    def rollback_impl(self, args, id_):
        try:
            subprocess.run(
                ['zfs', 'rollback'] + args + [id_], text=True, capture_output=True, check=True,
            )
        except subprocess.CalledProcessError as e:
            raise CallError(f'Failed to rollback snapshot: {e.stderr.strip()}')

    def hold(self, id_, options=None):
        """
        Holds snapshot `id`.

        `truenas` tag will be added to the snapshot's tag namespace.

        `options.recursive` (bool) will hold snapshots recursively.

        """
        options = options or {}
        try:
            with libzfs.ZFS() as zfs:
                snapshot = zfs.get_snapshot(id_)
                snapshot.hold('truenas', options.get('recursive', False))
        except libzfs.ZFSException as err:
            raise CallError(f'Failed to hold snapshot: {err}')

    def release(self, id_, options=None):
        """
        Release held snapshot `id`.

        Will remove all hold tags from the specified snapshot.

        `options.recursive` (bool) will release snapshots recursively. Only the tags that are present on the
            parent snapshot will be removed.

        """
        options = options or {}
        try:
            with libzfs.ZFS() as zfs:
                snapshot = zfs.get_snapshot(id_)
                for tag in snapshot.holds:
                    snapshot.release(tag, options.get('recursive', False))
        except libzfs.ZFSException as err:
            raise CallError(f'Failed to release snapshot: {err}')

    def rename(self, id_, new_name):
        try:
            with libzfs.ZFS() as zfs:
                snapshot = zfs.get_snapshot(id_)
                snapshot.rename(new_name)
        except libzfs.ZFSException as err:
            raise CallError(f'Failed to rename snapshot: {err}')

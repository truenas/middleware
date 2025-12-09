import libzfs
import subprocess

from middlewared.service import CallError, Service


class ZFSSnapshotService(Service):

    class Config:
        namespace = 'zfs.snapshot'
        process_pool = True
        private = True

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
            datasets = set()
            for i in self.middleware.call_sync(
                "zfs.resource.query_impl",
                {"paths": [dataset], "get_children": True, "properties": None}
            ):
                datasets.add(f'{i["name"]}@{snap_name}')

            for snap in filter(lambda sn: self.middleware.call_sync('zfs.resource.snapshot.query_impl', {'paths': [sn]}), datasets):
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

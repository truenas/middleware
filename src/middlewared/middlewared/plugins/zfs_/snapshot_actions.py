import libzfs
import subprocess

from middlewared.schema import accepts, Bool, Dict, returns, Str
from middlewared.service import CallError, private, Service


class ZFSSnapshot(Service):

    class Config:
        namespace = 'zfs.snapshot'
        process_pool = True

    @accepts(Dict(
        'snapshot_clone',
        Str('snapshot', required=True, empty=False),
        Str('dataset_dst', required=True, empty=False),
        Dict(
            'dataset_properties',
            additional_attrs=True,
        )
    ))
    def clone(self, data):
        """
        Clone a given snapshot to a new dataset.

        Returns:
            bool: True if succeed otherwise False.
        """

        snapshot = data.get('snapshot', '')
        dataset_dst = data.get('dataset_dst', '')
        props = data['dataset_properties']

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

    @accepts(
        Str('id'),
        Dict(
            'options',
            Bool('recursive', default=False),
            Bool('recursive_clones', default=False),
            Bool('force', default=False),
            Bool('recursive_rollback', default=False),
        ),
    )
    def rollback(self, id, options):
        """
        Rollback to a given snapshot `id`.

        `options.recursive` will destroy any snapshots and bookmarks more recent than the one
        specified.

        `options.recursive_clones` is just like `recursive` but will also destroy any clones.

        `options.force` will force unmount of any clones.

        `options.recursive_rollback` will do a complete recursive rollback of each child snapshots for `id`. If
        any child does not have specified snapshot, this operation will fail.
        """
        args = []
        if options['force']:
            args += ['-f']
        if options['recursive']:
            args += ['-r']
        if options['recursive_clones']:
            args += ['-R']

        if options['recursive_rollback']:
            dataset, snap_name = id.rsplit('@', 1)
            datasets = set({
                f'{ds["id"]}@{snap_name}' for ds in self.middleware.call_sync(
                    'zfs.dataset.query', [['OR', [['id', '^', f'{dataset}/'], ['id', '=', dataset]]]]
                )
            })

            for snap in filter(lambda sn: self.middleware.call_sync('zfs.snapshot.query', [['id', '=', sn]]), datasets):
                self.rollback_impl(args, snap)

        else:
            self.rollback_impl(args, id)

    @private
    def rollback_impl(self, args, id):
        try:
            subprocess.run(
                ['zfs', 'rollback'] + args + [id], text=True, capture_output=True, check=True,
            )
        except subprocess.CalledProcessError as e:
            raise CallError(f'Failed to rollback snapshot: {e.stderr.strip()}')

    @accepts(
        Str('id'),
        Dict(
            'options',
            Bool('recursive', default=False),
        ),
    )
    @returns()
    def hold(self, id, options):
        """
        Holds snapshot `id`.

        `truenas` tag will be added to the snapshot's tag namespace.

        `options.recursive` will hold snapshots recursively.
        """
        try:
            with libzfs.ZFS() as zfs:
                snapshot = zfs.get_snapshot(id)
                snapshot.hold('truenas', options['recursive'])
        except libzfs.ZFSException as err:
            raise CallError(f'Failed to hold snapshot: {err}')

    @accepts(
        Str('id'),
        Dict(
            'options',
            Bool('recursive', default=False),
        ),
    )
    @returns()
    def release(self, id, options):
        """
        Release held snapshot `id`.

        Will remove all hold tags from the specified snapshot.

        `options.recursive` will release snapshots recursively. Please note that only the tags that are present on the
        parent snapshot will be removed.
        """
        try:
            with libzfs.ZFS() as zfs:
                snapshot = zfs.get_snapshot(id)
                for tag in snapshot.holds:
                    snapshot.release(tag, options['recursive'])
        except libzfs.ZFSException as err:
            raise CallError(f'Failed to release snapshot: {err}')

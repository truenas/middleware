import errno
import libzfs

from middlewared.service import CallError, CRUDService, job, ValidationErrors
from middlewared.utils.filter_list import filter_list
from middlewared.utils.zfs import query_imported_fast_impl
from .pool_utils import convert_topology, find_vdev


class ZFSPoolService(CRUDService):

    class Config:
        namespace = 'zfs.pool'
        private = True
        process_pool = True

    def query(self, filters: list | None = None, options: dict | None = None):
        if filters is None:
            filters = list()
        if options is None:
            options = dict()

        # We should not get datasets, there is zfs.dataset.query for that
        state_kwargs = {'datasets_recursive': False}
        with libzfs.ZFS() as zfs:
            # Handle `id` or `name` filter specially to avoiding getting every property for all zpools
            if filters and len(filters) == 1 and list(filters[0][:2]) in (['id', '='], ['name', '=']):
                try:
                    pools = [zfs.get(filters[0][2]).asdict(**state_kwargs)]
                except libzfs.ZFSException:
                    pools = []
            else:
                pools = [i.asdict(**state_kwargs) for i in zfs.pools]
        return filter_list(pools, filters, options)

    def create(self, data: dict):
        """
        Create a zpool.
            Cf. `pool.create` public endpoint for schema documentation'
        """
        data.setdefault('options', dict())
        data.setdefault('fsoptions', dict())
        with libzfs.ZFS() as zfs:
            topology = convert_topology(zfs, data['vdevs'])
            zfs.create(data['name'], topology, data['options'], data['fsoptions'])
        return self.middleware.call_sync('zfs.pool.get_instance', data['name'])

    def update(self, name: str, options: dict | None = None):
        """
        Update a zpool.
            Cf. `pool.update` public endpoint for schema documentation'
        """
        if options is None:
            options = dict()

        options.setdefault('properties', dict())
        try:
            with libzfs.ZFS() as zfs:
                pool = zfs.get(name)
                for k, v in options['properties'].items():
                    prop = pool.properties[k]
                    if 'value' in v:
                        prop.value = v['value']
                    elif 'parsed' in v:
                        prop.parsed = v['parsed']
        except libzfs.ZFSException as e:
            raise CallError(str(e))
        else:
            return options

    def delete(self, name: str, options: dict | None = None):
        """
        Delete a zpool.
            Cf. `pool.delete` public endpoint for schema documentation'
        """
        if options is None:
            options = dict()
        options.setdefault('force', False)
        try:
            with libzfs.ZFS() as zfs:
                zfs.destroy(name, force=options['force'])
        except libzfs.ZFSException as e:
            errno_ = errno.EFAULT
            if e.code == libzfs.Error.UMOUNTFAILED:
                errno_ = errno.EBUSY
            raise CallError(str(e), errno_)
        else:
            return True

    @job()
    def extend(
        self,
        job,
        name: str,
        new: list[str] | None = None,
        existing: list[dict[str, str]] | None = None
    ):
        """
        Extend a zpool.
            Cf. `pool.extend` public endpoint for schema documentation'
        """
        if new is None and existing is None:
            raise CallError('New or existing vdevs must be provided', errno.EINVAL)

        try:
            with libzfs.ZFS() as zfs:
                pool = zfs.get(name)

                if new:
                    topology = convert_topology(zfs, new)
                    pool.attach_vdevs(topology)

                # Make sure we can find all target vdev
                for i in (existing or []):
                    target = find_vdev(pool, i['target'])
                    if target is None:
                        raise CallError(f"Failed to find vdev for {i['target']}", errno.EINVAL)
                    i['target'] = target

                for i in (existing or []):
                    newvdev = libzfs.ZFSVdev(zfs, i['type'].lower())
                    newvdev.path = i['path']
                    i['target'].attach(newvdev)

        except libzfs.ZFSException as e:
            raise CallError(str(e), e.code)

    def query_imported_fast(self, name_filters=None):
        # the equivalent of running `zpool list -H -o guid,name` from cli
        # name_filters will be a list of pool names
        return query_imported_fast_impl(name_filters)

    def validate_draid_configuration(self, topology_type, numdisks, nparity, vdev):
        verrors = ValidationErrors()
        try:
            libzfs.validate_draid_configuration(
                numdisks, nparity, vdev['draid_spare_disks'], vdev['draid_data_disks'],
            )
        except libzfs.ZFSException as e:
            verrors.add(
                f'topology.{topology_type}.type',
                str(e),
            )

        return verrors

import libzfs

from middlewared.schema import accepts, Str
from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list


class ZFSPoolService(CRUDService):

    class Config:
        namespace = 'zfs.pool'
        private = True
        process_pool = True

    @filterable
    def query(self, filters, options):
        # We should not get datasets, there is zfs.dataset.query for that
        state_kwargs = {'datasets_recursive': False}
        with libzfs.ZFS() as zfs:
            # Handle `id` or `name` filter specially to avoiding getting every property for all zpools
            if filters and len(filters) == 1 and list(filters[0][:2]) in (['id', '='], ['name', '=']):
                try:
                    pools = [zfs.get(filters[0][2]).__getstate__(**state_kwargs)]
                except libzfs.ZFSException:
                    pools = []
            else:
                pools = [i.__getstate__(**state_kwargs) for i in zfs.pools]
        return filter_list(pools, filters, options)

    def query_imported_fast(self, name_filters=None):
        # the equivalent of running `zpool list -H -o guid,name` from cli
        # name_filters will be a list of pool names
        out = {}
        name_filters = name_filters or []
        with os.scandir('/proc/spl/kstat/zfs') as it:
            for entry in filter(lambda entry: not name_filters or entry.name in name_filters, it):
                if not entry.is_dir() or entry.name == '$import':
                    continue

                guid = self.guid_fast(entry.name)
                state = self.state_fast(entry.name)
                out.update({guid: {'name': entry.name, 'state': state}})

        return out

    @accepts(Str('pool'))
    def guid_fast(self, pool):
        """
        Lockless read of zpool guid. Raises FileNotFoundError
        if pool not imported.
        """
        with open(f'/proc/spl/kstat/zfs/{pool}/guid') as f:
            guid_out = f.read()

        return guid_out.strip()

    @accepts(Str('pool'))
    def state_fast(self, pool):
        """
        Lockless read of zpool state. Raises FileNotFoundError
        if pool not imported.
        """
        with open(f'/proc/spl/kstat/zfs/{pool}/state') as f:
            state = f.read()

        return state.strip()

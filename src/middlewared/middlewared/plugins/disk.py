from middlewared.schema import accepts, Ref
from middlewared.service import private, Service


class DiskService(Service):

    @accepts(Ref('query-filters'), Ref('query-options'))
    def query(self, filters=None, options=None):
        if filters is None:
            filters = []
        if options is None:
            options = {}
        filters.append(('disk_enabled', '=', True))
        options['extend'] = 'disk.disk_extend'
        return self.middleware.call('datastore.query', 'storage.disk', filters, options)

    @private
    def disk_extend(self, disk):
        """
        This is a compatiblity method to remove superfluous "disk_" suffix from attributes
        from the Django datastore
        """
        for k, v in disk.items():
            if k.startswith('disk_'):
                del disk[k]
                disk[k[5:]] = v
        # enabled is an internal attribute that does not need to be exposed
        disk.pop('enabled', None)
        return disk

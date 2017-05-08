from middlewared.service import filterable, private, CRUDService


class DiskService(CRUDService):

    @filterable
    def query(self, filters=None, options=None):
        if filters is None:
            filters = []
        if options is None:
            options = {}
        options['prefix'] = 'disk_'
        filters.append(('enabled', '=', True))
        options['extend'] = 'disk.disk_extend'
        return self.middleware.call('datastore.query', 'storage.disk', filters, options)

    @private
    def disk_extend(self, disk):
        disk.pop('enabled', None)
        return disk

from middlewared.service import lock, Service


class ReportingService(Service):

    class Config:
        private = True

    @lock('reporting.cleanup')
    def cleanup(self):
        sysds = self.middleware.call_sync('systemdataset.config')
        if not sysds['path']:
            self.logger.error('System dataset is not mounted')
            return False

        filters = [['name', 'rin', 'rrd-']]
        options = {'extra': {'retrieve_properties': False}}
        for ds in self.middleware.call_sync('zfs.dataset.query', filters, options):
            # when we ran collectd/rrdcached we symlinked the collectd config
            # directory to a /var/db/system/rrd-{uuid} dataset as well as symlinking
            # the rrdcached config to the same place. Since those daemons were
            # removed, we need to clean up the datasets.
            try:
                self.middleware.call_sync('zfs.dataset.delete', ds['id'], {'force': True, 'recursive': True})
            except Exception:
                self.logger.warning('Failed to clean up unused dataset %r', ds['id'], exc_info=True)
                continue

        return True

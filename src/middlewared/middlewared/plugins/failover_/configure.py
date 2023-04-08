from middlewared.service import Service

HA_LICENSE_CACHE_KEY = 'LICENSED_FOR_HA'


class FailoverConfigureService(Service):

    class Config:
        namespace = 'failover.configure'
        private = True

    def license(self, dser_lic):
        """
            1. cache locally whether or not this is a HA license
            2. if this is a HA license:
                --ensure we populate IP of heartbeat iface for remote node
                --ensure we tell remote node to populate IP of heartbeat iface for local node
                --copy the license file to the remote node
                --invalidate the license cache on the remote node
                --enable/disable systemd services on the remote node
        """
        is_ha = bool(dser_lic.system_serial_ha)
        self.middleware.call_sync('cache.put', HA_LICENSE_CACHE_KEY, is_ha)
        if is_ha:
            try:
                self.middleware.call_sync('failover.ensure_remote_client')
            except Exception:
                # this is fatal because we can't determine what the remote ip address
                # is to so any failover.call_remote calls will fail
                self.logger.error('Failed to determine remote heartbeat IP address', exc_info=True)
                return

            try:
                self.middleware.call_sync('failover.call_remote', 'failover.ensure_remote_client')
            except Exception:
                # this is not fatal, so no reason to return early
                # it just means that any "failover.call_remote" calls initiated from the remote node
                # will fail but that shouldn't be happening anyways
                self.logger.warning('Remote node failed to determine this nodes heartbeat IP address', exc_info=True)

            try:
                self.middleware.call_sync('failover.send_small_file', self.middleware.call_sync('system.license_path'))
            except Exception:
                self.logger.warning('Failed to sync database to remote node', exc_info=True)
                return

            try:
                self.middleware.call_sync('failover.call_remote', 'cache.pop', [HA_LICENSE_CACHE_KEY])
            except Exception:
                self.logger.warning('Failed to invalidate license cache on remote node', exc_info=True)

            try:
                self.middleware.call_sync('failover.call_remote', 'etc.generate', ['rc'])
            except Exception:
                self.logger.warning('etc.generate failed on standby', exc_info=True)

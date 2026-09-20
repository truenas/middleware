from middlewared.api import api_method
from middlewared.api.current import PoolDatasetProcessesArgs, PoolDatasetProcessesResult
from middlewared.service import Service, private


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @api_method(PoolDatasetProcessesArgs, PoolDatasetProcessesResult, roles=['DATASET_READ'])
    async def processes(self, oid):
        """
        Return a list of processes using this dataset.

        Example return value::

            [
              {
                "pid": 2520,
                "name": "smbd",
                "service": "cifs"
              },
              {
                "pid": 97778,
                "name": "minio",
                "cmdline": "/usr/local/bin/minio -C /usr/local/etc/minio server --address=0.0.0.0:9000 /mnt/tank/wk"
              }
            ]
        """
        return await self.call2(self.s.zfs.resource.processes, oid)

    @private
    async def kill_processes(self, oid, control_services, max_tries=5):
        return await self.call2(self.s.zfs.resource.kill_processes, oid, control_services, max_tries)

    @private
    def processes_using_paths(self, paths, include_paths=False, include_middleware=False, devices=None):
        return self.call_sync2(
            self.s.zfs.resource.processes_using_paths, paths, include_paths, include_middleware, devices
        )

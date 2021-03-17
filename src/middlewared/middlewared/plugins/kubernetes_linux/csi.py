from middlewared.service import ConfigService


class KubernetesCSIService(ConfigService):

    class Config:
        namespace = 'k8s.csi'
        private = True

    async def check_state(self, resource, ready_key, available_key):
        ready = resource['status'][ready_key]
        available = resource['status'][available_key]
        return ready and available and ready >= available

    async def config(self):
        # We would like to see if zfs-localpv is setup and we have pods working
        # daemonset - openebs-zfs-node
        # statefulset - openebs-zfs-controller
        zfs_ds_ready = zfs_ss_ready = False
        zfs_ds = await self.middleware.call('k8s.daemonset.query', [['metadata.name', '=', 'openebs-zfs-node']])
        if zfs_ds:
            zfs_ds_ready = await self.check_state(zfs_ds[0], 'number_ready', 'number_available')

        zfs_ss = await self.middleware.call('k8s.statefulset.query', [['metadata.name', '=', 'openebs-zfs-controller']])
        if zfs_ss:
            zfs_ss_ready = await self.check_state(zfs_ss[0], 'ready_replicas', 'replicas')

        return {
            'csi_ready': zfs_ds_ready and zfs_ss_ready,
        }

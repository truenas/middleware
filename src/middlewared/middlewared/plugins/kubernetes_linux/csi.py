from middlewared.service import ConfigService


class KubernetesCSIService(ConfigService):

    class Config:
        namespace = 'k8s.csi'
        private = True

    async def config(self):
        # We would like to see if zfs-localpv is setup and we have pods working
        # daemonset - openebs-zfs-node
        # statefulset - openebs-zfs-controller
        zfs_ds_ready = zfs_ss_ready = False
        zfs_ds = await self.middleware.call('k8s.daemonset.query', [['metadata.name', '=', 'openebs-zfs-node']])
        if zfs_ds and zfs_ds[0]['status']['ready_replicas'] >= zfs_ds[0]['status']['replicas']:
            zfs_ds_ready = True

        zfs_ss = await self.middleware.call('k8s.statefulset.query', [['metadata.name', '=', 'openebs-zfs-controller']])
        if zfs_ss and zfs_ss[0]['status']['ready_replicas'] >= zfs_ss[0]['status']['replicas']:
            zfs_ss_ready = True

        return {
            'csi_ready': zfs_ds_ready and zfs_ss_ready,
        }

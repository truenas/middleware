from middlewared.service import Service
from middlewared.plugins.cluster_linux.utils import CTDBConfig

from pathlib import Path


class CtdbInitService(Service):

    class Config:
        namespace = 'ctdb.setup'
        private = True

    async def init(self):
        """
        Initialize all the necessary components
        for ctdb cluster.
        """

        result = {'logit': True, 'success': False}
        if not await self.middleware.call('service.started', 'glusterd'):
            return result

        shared_vol = Path(CTDBConfig.CTDB_LOCAL_MOUNT.value)
        try:
            mounted = shared_vol.is_mount()
        except Exception:
            # can happen if shared volume is mounted but
            # glusterd service is stopped/crashed etc
            self.logger.error('Checking if %s is mounted failed', str(shared_vol), exc_info=True)
            return result

        # if the cluster shared volume isn't FUSE mounted, then
        # there is no reason to continue
        if not mounted:
            self.logger.warning('%s is not mounted', str(shared_vol))
            return result

        if not await self.middleware.call('ctdb.setup.general'):
            return result

        return await self.middleware.call('ctdb.setup.ip_files', result)

    async def general(self):
        """
        Write /etc/ctdb/ctdb.conf
        """

        await self.middleware.call('etc.generate', 'ctdb')
        return Path(CTDBConfig.ETC_GEN_FILE.value).exists()

    def ip_files(self, result):

        pri_e_file = Path(CTDBConfig.ETC_PRI_IP_FILE.value)
        pri_c_file = Path(CTDBConfig.GM_PRI_IP_FILE.value)
        pub_e_file = Path(CTDBConfig.ETC_PUB_IP_FILE.value)
        pub_c_file = Path(CTDBConfig.GM_PUB_IP_FILE.value)

        # the private ip file is the only ip file
        # that is needed for ctdb to be started
        # so check for it's existence first.
        # if the private ip file doesn't exist on
        # the ctdb shared volume, then that means
        # no private peers have been added to the
        # cluster. We don't continue because the
        # ctdb.private.ips.create method is
        # responsible for creating this file.
        if not pri_c_file.exists():
            result['logit'] = False
            return result
        else:
            # we symlink this file which means
            # it has to be removed first. If we
            # fail doing that for whatever reason
            # then nothing else will work
            try:
                pri_e_file.unlink(missing_ok=True)
            except Exception:
                self.logger.error('Failed to remove %s', str(pri_e_file), exc_info=True)
                return result

            try:
                pri_e_file.symlink_to(pri_c_file)
            except Exception:
                self.logger.error('Failed to symlink %s to %s', str(pri_e_file), str(pri_c_file), exc_info=True)
                return result

        # now handle the public IP file
        # the ctdb daemon can be started without a public ip
        # file so long as the private ip file exist
        # If we get here and it doesn't exist, then return
        # True
        if not pub_c_file.exists():
            result['logit'] = False
            return result
        else:
            try:
                # we symlink this file which means
                # it has to be removed first. If we
                # fail doing that for whatever reason
                # then play it safe and return result
                pub_e_file.unlink(missing_ok=True)
            except Exception:
                self.logger.error('Failed to remove %s', str(pub_e_file), exc_info=True)
                return result

            try:
                pub_e_file.symlink_to(pub_c_file)
            except Exception:
                self.logger.error('Failed to symlink %s to %s', str(pub_e_file), str(pub_c_file), exc_info=True)
                return result

        result['logit'] = False
        result['success'] = True

        return result

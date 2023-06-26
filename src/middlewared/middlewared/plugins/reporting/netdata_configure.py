import os

from middlewared.service import lock, private, Service
from middlewared.utils.shutil import rmtree_one_filesystem


class ReportingService(Service):

    NETDATA_UID = None
    NETDATA_GID = None

    @private
    async def cache_netdata_uid_gid(self):
        user_obj = await self.middleware.call('user.get_user_obj', {'username': 'netdata'})
        self.NETDATA_UID = user_obj['pw_uid']
        self.NETDATA_GID = user_obj['pw_gid']

    @private
    def netdata_storage_location(self):
        systemdataset_config = self.middleware.call_sync('systemdataset.config')
        if not systemdataset_config['path']:
            return None

        return f'{systemdataset_config["path"]}/netdata-{systemdataset_config["uuid"]}'

    @private
    @lock('netdata_configure')
    def netdata_setup(self):
        netdata_mount = self.netdata_storage_location() or ''
        if not os.path.exists(netdata_mount):
            self.logger.error('%r does not exist or is not a directory', netdata_mount)
            return False

        # Ensure that netdata working path is a symlink to system dataset
        pwd = '/var/cache/netdata'
        if os.path.islink(pwd):
            if os.path.realpath(pwd) != netdata_mount:
                os.unlink(pwd)
        else:
            if os.path.exists(pwd):
                rmtree_one_filesystem(pwd)

        if not os.path.exists(pwd):
            os.symlink(netdata_mount, pwd)

        # We will make sure now that netdata user/group has access to this directory
        self.middleware.call_sync('filesystem.acltool', pwd, 'chown', self.NETDATA_UID, self.NETDATA_GID, {
            'recursive': True,
            'posixacl': True,
        })
        os.makedirs('/var/log/netdata', exist_ok=True)
        self.middleware.call_sync(
            'filesystem.acltool', '/var/log/netdata', 'chown',
            self.NETDATA_UID, self.NETDATA_GID, {
                'recursive': True,
                'posixacl': True,
            }
        )

        return True


async def setup(middleware):
    await middleware.call('reporting.cache_netdata_uid_gid')

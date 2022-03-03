import os

from middlewared.service import private, Service
from middlewared.utils.shutil import rmtree_one_filesystem


class ReportingService(Service):
    @private
    def hostname(self):
        network_config = self.middleware.call_sync('network.configuration.config')
        return f"{network_config['hostname_local']}.{network_config['domain']}"

    @private
    def setup(self):
        systemdatasetconfig = self.middleware.call_sync('systemdataset.config')
        if not systemdatasetconfig['path']:
            self.middleware.logger.error('System dataset is not mounted')
            return False

        rrd_mount = f'{systemdatasetconfig["path"]}/rrd-{systemdatasetconfig["uuid"]}'
        if not os.path.exists(rrd_mount):
            self.middleware.logger.error(f'{rrd_mount} does not exist or is not a directory')
            return False

        # Ensure that collectd working path is a symlink to system dataset
        base_collectd = '/var/db/collectd'
        pwd = os.path.join(base_collectd, 'rrd')
        if os.path.islink(pwd):
            if os.path.realpath(pwd) != rrd_mount:
                os.unlink(pwd)
        else:
            if os.path.exists(pwd):
                rmtree_one_filesystem(pwd)
        if not os.path.exists(pwd):
            os.makedirs(base_collectd, exist_ok=True)
            os.symlink(rrd_mount, pwd)

        # We want to store all our reporting data in `localhost` directory and make `$hostname` directory
        # (that collectd uses without offering any alternatives) a symlink to `localhost`.
        for item in os.listdir(pwd):
            path = os.path.join(pwd, item)

            if item == 'journal':
                # Keep rrdcached journal
                continue

            if item == 'localhost':
                # `localhost` should be a directory
                if os.path.islink(path):
                    os.unlink(path)

                continue

            # Remove all symlinks (that are stale if hostname was changed)
            # Remove all files and directories except "localhost" (that may be erroneously created by
            # running collectd before this script)
            rmtree_one_filesystem(path)

        os.makedirs(os.path.join(pwd, 'localhost'), exist_ok=True)
        os.symlink(os.path.join(pwd, 'localhost'), os.path.join(pwd, self.hostname()))

        # Let's return a positive value to indicate that necessary collectd operations were performed successfully
        return True

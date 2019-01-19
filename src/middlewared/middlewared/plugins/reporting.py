import copy
import os
import shutil
import subprocess
import tarfile
import time

import humanfriendly
import psutil
import sysctl

from middlewared.schema import accepts, Bool, Dict, Int, List, Str, ValidationErrors
from middlewared.service import ConfigService, private
from middlewared.utils import run
from middlewared.validators import Range

SYSRRD_SENTINEL = '/data/sentinels/sysdataset-rrd-disable'


def remove(path, link_only=False):
    if os.path.exists(path):
        if os.path.islink(path):
            os.unlink(path)
        elif os.path.isdir(path) and not link_only:
            shutil.rmtree(path)
        elif not link_only:
            os.remove(path)


def get_members(tar, prefix):
    for tarinfo in tar.getmembers():
        if tarinfo.name.startswith(prefix):
            tarinfo.name = tarinfo.name[len(prefix):]
            yield tarinfo


def rename_tarinfo(tarinfo):
    name = tarinfo.name.split('/', maxsplit=4)
    tarinfo.name = f'collectd/rrd/{"" if len(name) < 5 else name[-1]}'
    return tarinfo


class ReportingService(ConfigService):

    class Config:
        datastore = 'system.reporting'
        datastore_extend = 'reporting.extend'

    @private
    async def extend(self, data):
        size = 0

        # Each disk consumes about 1.7MB (geom_stat) + 1.1MB(disk) of space
        # so we need bigger tmpfs on systems with lots of disks.
        no_disks = len(sysctl.filter('kern.disks')[0].value.split())
        size += no_disks * 2.8

        # Each CPU takes about 1MB
        no_cpus = sysctl.filter('kern.smp.cpus')[0].value
        size += no_cpus * 1

        # This all was true for RRARows 1200 and five RRATimespan
        size /= (1200 / data['graph_rows'])
        size /= (5 / len(data['graph_timespans']))

        data['rrd_size_alert_threshold_suggestion'] = (300 + int(size)) * 1024 * 1024
        return data

    @accepts(
        Dict(
            'reporting_update',
            Bool('rrd_usedataset'),
            Int('rrd_size_alert_threshold', null=True),
            Bool('cpu_in_percentage'),
            Str('graphite'),
            Int('rrd_ramdisk_size', validators=[Range(min=1)]),
            List('graph_timespans', items=[Int('timespan', validators=[Range(min=1)])], empty=False, unique=True),
            Int('graph_rows', validators=[Range(min=1)]),
            Bool('confirm_rrd_destroy'),
            update=True
        )
    )
    async def do_update(self, data):
        """
        Configure Reporting Database settings.

        `rrd_usedataset` is a flag that determines whether reporting database is located in system dataset or on
        RAMDisk.

        `rrd_size_alert_threshold` is a size (in bytes) of reporting database that will trigger an alert. It can be
        set to null, then an auto-calculated default is used, suitable for most use cases. This value is present in
        `reporting.config` result as `rrd_size_alert_threshold_suggestion`.

        If `cpu_in_percentage` is `true`, collectd will report CPU usage in percentage instead of "jiffies".

        `graphite` specifies a hostname or IP address that will be used as the destination to send collectd data
        using the graphite plugin.

        `rrd_ramdisk_size` specifies size (in bytes) for RAMDisk if `rrd_usedataset` is unchecked.

        `graph_timespans` and `graph_rows` correspond to collectd `RRARows` and `RRATimespan` options. Changing these
        will require destroying your current reporting database so when these fields are changed, an additional
        `confirm_rrd_destroy: true` flag must be present

        .. examples(websocket)::

          Update reporting settings

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "reporting.update",
                "params": [{
                    "rrd_usedataset": true,
                    "rrd_size_alert_threshold": null,
                    "cpu_in_percentage": false,
                    "graphite": "",
                    "rrd_ramdisk_size": 1073741824,
                }]
            }

          Recreate reporting database with new settings

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "reporting.update",
                "params": [{
                    "graph_timespans": [3600, 86400, 604800, 2678400, 31622400],
                    "graph_rows": 1200,
                    "confirm_rrd_destroy": true,
                }]
            }
        """

        confirm_rrd_destroy = data.pop('confirm_rrd_destroy', False)

        old = await self.config()
        old.pop('rrd_size_alert_threshold_suggestion')

        new = copy.deepcopy(old)
        new.update(data)

        verrors = ValidationErrors()

        data_dir = '/var/db/collectd/rrd'
        update_ramdisk = False
        if old['rrd_ramdisk_size'] != new['rrd_ramdisk_size']:
            disk_parts = psutil.disk_partitions()
            data_dir_is_ramdisk = len([d for d in disk_parts if d.mountpoint == data_dir and d.device == 'tmpfs']) > 0
            if data_dir_is_ramdisk:
                update_ramdisk = True

                used = psutil.disk_usage(data_dir).used
                if new['rrd_ramdisk_size'] < used:
                    verrors.add(
                        'reporting_update.rrd_ramdisk_size',
                        f'Your current RAMDisk usage is {humanfriendly.format_size(used)} ({used} bytes), you can\'t '
                        f'set RAMDisk size below this value'
                    )

        destroy_database = False
        for k in ['graph_timespans', 'graph_rows']:
            if old[k] != new[k]:
                destroy_database = True

                if not confirm_rrd_destroy:
                    verrors.add(
                        f'reporting_update.{k}',
                        f'Changing this option requires destroying of reporting database so you\'ll have to confirm '
                        f'this action by setting corresponding flag',
                    )

        if verrors:
            raise verrors

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            old['id'],
            new,
            {'prefix': self._config.datastore_prefix}
        )

        if old['rrd_usedataset'] != new['rrd_usedataset']:
            await self.middleware.call('service.stop', 'collectd')
            await self._rrd_toggle()

        if update_ramdisk:
            await self.middleware.call('service.stop', 'collectd')
            await run('/usr/local/sbin/save_rrds.sh', check=False)
            await run('umount', data_dir, check=False)

        if destroy_database:
            await self.middleware.call('service.stop', 'collectd')
            await run('sh', '-c', 'rm /data/rrd_dir.tar.bz2', check=False)
            await run('sh', '-c', 'rm -rf /var/db/collectd/rrd/*', check=False)

        await self.middleware.call('service.restart', 'collectd')

        return await self.config()

    async def _rrd_toggle(self):
        config = await self.config()
        systemdatasetconfig = await self.middleware.call('systemdataset.config')

        # Path where collectd stores files
        rrd_path = '/var/db/collectd/rrd'
        # Path where rrd fies are stored in system dataset
        rrd_syspath = f'/var/db/system/rrd-{systemdatasetconfig["uuid"]}'

        if config['rrd_usedataset']:
            # Move from tmpfs to system dataset
            if os.path.exists(rrd_path):
                if os.path.islink(rrd_path):
                    # rrd path is already a link
                    # so there is nothing we can do about it
                    return False
                cp = await run('rsync', '-a', f'{rrd_path}/', f'{rrd_syspath}/', check=False)
                return cp.returncode == 0
        else:
            # Move from system dataset to tmpfs
            if os.path.exists(rrd_path):
                if os.path.islink(rrd_path):
                    os.unlink(rrd_path)
            else:
                os.makedirs(rrd_path)
            cp = await run('rsync', '-a', f'{rrd_syspath}/', f'{rrd_path}/', check=False)
            return cp.returncode == 0
        return False

    @private
    def use_rrd_dataset(self):
        config = self.middleware.call_sync('reporting.config')
        systemdatasetconfig = self.middleware.call_sync('systemdataset.config')
        is_freenas = self.middleware.call_sync('system.is_freenas')
        rrd_mount = ''
        if systemdatasetconfig['path']:
            rrd_mount = f'{systemdatasetconfig["path"]}/rrd-{systemdatasetconfig["uuid"]}'

        use_rrd_dataset = False
        if (
            rrd_mount and config['rrd_usedataset'] and (
                is_freenas or (not is_freenas and self.middleware.call_sync('failover.status') != 'BACKUP')
            )
        ):
            use_rrd_dataset = True

        return use_rrd_dataset

    @private
    def update_collectd_dataset(self):
        config = self.middleware.call_sync('reporting.config')
        systemdatasetconfig = self.middleware.call_sync('systemdataset.config')
        is_freenas = self.middleware.call_sync('system.is_freenas')
        rrd_mount = ''
        if systemdatasetconfig['path']:
            rrd_mount = f'{systemdatasetconfig["path"]}/rrd-{systemdatasetconfig["uuid"]}'

        use_rrd_dataset = self.use_rrd_dataset()

        # If not is_freenas remove the rc.conf cache rc.conf.local will
        # run again using the correct collectd_enable. See #5019
        if not is_freenas:
            try:
                os.remove('/var/tmp/freenas_config.md5')
            except FileNotFoundError:
                pass

        hostname = self.middleware.call_sync('system.info')['hostname']
        if not hostname:
            hostname = self.middleware.call_sync('network.configuration.config')['hostname']

        rrd_file = '/data/rrd_dir.tar.bz2'
        data_dir = '/var/db/collectd/rrd'
        disk_parts = psutil.disk_partitions()
        data_dir_is_ramdisk = len([d for d in disk_parts if d.mountpoint == data_dir and d.device == 'tmpfs']) > 0

        if use_rrd_dataset:
            if os.path.isdir(rrd_mount):
                if os.path.isdir(data_dir) and not os.path.islink(data_dir):
                    if data_dir_is_ramdisk:
                        # copy-umount-remove
                        subprocess.Popen(
                            ['cp', '-a', data_dir, f'{data_dir}.{time.strftime("%Y%m%d%H%M%S")}'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE
                        ).communicate()

                        # Should we raise an exception if umount fails ?
                        subprocess.Popen(
                            ['umount', data_dir],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE
                        ).communicate()

                        remove(data_dir)
                    else:
                        shutil.move(data_dir, f'{data_dir}.{time.strftime("%Y%m%d%H%M%S")}')

                if os.path.realpath(data_dir) != rrd_mount:
                    remove(data_dir)
                    os.symlink(rrd_mount, data_dir)
            else:
                self.middleware.logger.error(f'{rrd_mount} does not exist or is not a directory')
                return None
        else:
            remove(data_dir, link_only=True)

            if not os.path.isdir(data_dir):
                os.makedirs(data_dir)

            # Create RAMdisk (if not already exists) for RRD files so they don't fill up root partition
            if not data_dir_is_ramdisk:
                subprocess.Popen(
                    ['mount', '-t', 'tmpfs', '-o', f'size={config["rrd_ramdisk_size"]}', 'tmpfs', data_dir],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                ).communicate()

        pwd = rrd_mount if use_rrd_dataset else data_dir
        if not os.path.exists(pwd):
            self.middleware.logger.error(f'{pwd} does not exist')
            return None

        if os.path.isfile(rrd_file):
            with tarfile.open(rrd_file) as tar:
                if 'collectd/rrd' in tar.getnames():
                    tar.extractall(pwd, get_members(tar, 'collectd/rrd/'))

            if use_rrd_dataset:
                remove(rrd_file)

        # Migrate from old version, where "${hostname}" was a real directory
        # and "localhost" was a symlink.
        # Skip the case where "${hostname}" is "localhost", so symlink was not
        # (and is not) needed.
        if (
            hostname != 'localhost' and os.path.isdir(os.path.join(pwd, hostname)) and not os.path.islink(
                os.path.join(pwd, hostname)
            )
        ):
            if os.path.exists(os.path.join(pwd, 'localhost')):
                if os.path.islink(os.path.join(pwd, 'localhost')):
                    remove(os.path.join(pwd, 'localhost'))
                else:
                    # This should not happen, but just in case
                    shutil.move(
                        os.path.join(pwd, 'localhost'),
                        os.path.join(pwd, f'localhost.bak.{time.strftime("%Y%m%d%H%M%S")}')
                    )
            shutil.move(os.path.join(pwd, hostname), os.path.join(pwd, 'localhost'))

        # Remove all directories except "localhost" and it's backups (that may be erroneously created by
        # running collectd before this script)
        to_remove_dirs = [
            os.path.join(pwd, d) for d in os.listdir(pwd)
            if not d.startswith('localhost') and os.path.isdir(os.path.join(pwd, d))
        ]
        for r_dir in to_remove_dirs:
            remove(r_dir)

        # Remove all symlinks (that are stale if hostname was changed).
        to_remove_symlinks = [
            os.path.join(pwd, l) for l in os.listdir(pwd)
            if os.path.islink(os.path.join(pwd, l))
        ]
        for r_symlink in to_remove_symlinks:
            remove(r_symlink)

        # Create "localhost" directory if it does not exist
        if not os.path.exists(os.path.join(pwd, 'localhost')):
            os.makedirs(os.path.join(pwd, 'localhost'))

        # Create "${hostname}" -> "localhost" symlink if necessary
        if hostname != 'localhost':
            os.symlink(os.path.join(pwd, 'localhost'), os.path.join(pwd, hostname))

        # Let's return a positive value to indicate that necessary collectd operations were performed successfully
        return True

    @private
    def sysrrd_disable(self):
        # skip if no sentinel is found
        if os.path.exists(SYSRRD_SENTINEL):
            systemdataset_config = self.middleware.call_sync('systemdataset.config')
            rrd_mount = f'{systemdataset_config["path"]}/rrd-{systemdataset_config["uuid"]}'
            if os.path.isdir(rrd_mount):
                # Let's create tar from system dataset rrd which collectd.conf understands
                with tarfile.open('/data/rrd_dir.tar.bz2', mode='w:bz2') as archive:
                    archive.add(rrd_mount, filter=rename_tarinfo)

            os.remove(SYSRRD_SENTINEL)

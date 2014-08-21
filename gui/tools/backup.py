#!/usr/bin/env python
#+
# Copyright 2014 Jakub Klama <jceel@FreeBSD.org>
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

import argparse
import datetime
import fcntl
import gzip
import logging
import logging.config
import os
import os.path
import pydoc
import signal
import shutil
import subprocess
import sys
import socket
import SocketServer
import stat
import re
import tempfile
import threading
import time
import json
from paramiko import ssh_exception, sftp_client, transport, pkey, rsakey, dsskey

import daemon

HERE = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(HERE, ".."))
sys.path.append(os.path.join(HERE, "../.."))
sys.path.append('/usr/local/www')
sys.path.append('/usr/local/www/freenasUI')

os.environ['DJANGO_SETTINGS_MODULE'] = 'freenasUI.settings'

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.storage.models import Volume, Disk, MountPoint
from freenasUI.system.models import Backup
from freenasUI.settings import LOGGING
from freenasUI.middleware import notifier
from freenasUI.common import humanize_size

progress_old_done = 0
progress_old_time = None
log = logging.getLogger('tools.backup')
logging.config.dictConfig(LOGGING)

DATABASEFILE = '/data/freenas-v1.db'
DBFILE = '/data/freenas-v1.db'
PIDFILE = '/var/run/backupd.pid'
SOCKFILE = '/var/run/backupd.sock'
VERSIONFILE = '/etc/version'
BUFSIZE = 16384

def main_loop():

    if os.path.exists(SOCKFILE):
        os.unlink(SOCKFILE)

    server = SocketServer.UnixStreamServer(SOCKFILE, CommandHandler)
    server.context = BackupContext()
    server.context.shutdown = server.shutdown
    os.chmod(SOCKFILE, 0o700)
    server.serve_forever()

class BackupContext:
    def __init__(self):
        self.backup_thread = None
        self.shutdown = None
        self.active = False
        self.failed = False
        self.finished = False
        self.hostport = None
        self.username = None
        self.password = None
        self.remote_directory = None
        self.use_key = False
        self.backup_data = False
        self.compressed = False
        self.status_msg = None
        self.failed_msg = None
        self.estimated_size = 0
        self.done_size = 0

class CommandHandler(SocketServer.StreamRequestHandler):
    def setup(self):
        self.context = self.server.context
        return SocketServer.StreamRequestHandler.setup(self)

    def handle(self):
        while True:
            command = self.rfile.readline().strip()
            if not command:
                break

            try:
                args = json.loads(command)
            except ValueError:
                self.respond(status='ERROR', msg='Unreadable command')
                continue

            commands = {
                'START': self.cmd_start,
                'PROGRESS': self.cmd_progress,
                'ABORT': self.cmd_abort
            }

            cmdname = args.pop('cmd')
            if not cmdname in commands.keys():
                self.respond(status='ERROR', msg='Unknown command')
                continue

            commands[cmdname](args)

    def respond(self, **kwargs):
        response = json.dumps(kwargs)
        self.wfile.write(response + '\n')

    def cmd_start(self, args):
        """
        Start a backup using credentials and destination path passed in args.
        """
        self.context.hostport = args.pop('hostport')
        self.context.username = args.pop('username')
        self.context.password = args.pop('password', None)
        self.context.remote_directory = args.pop('directory')
        self.context.backup_data = args.pop('with-data')
        self.context.compressed = args.pop('compression')
        self.context.use_key = args.pop('use-keys')

        bid = args.pop('backup-id')
        backup = Backup.objects.get(id=bid)

        self.context.backup_thread = BackupWorker(self.context, backup)
        self.context.backup_thread.start()
        
        self.respond(status='OK', msg='Backup started')
        
    def cmd_progress(self, args):
        """
        Respond with backup progress if any backup is active right now or
        return error if not.
        """
        if not self.context.active:
            self.respond(status="ERROR", msg="No backup is currently pending")
            return

        self.respond(
            status="OK",
            done=self.context.done_size,
            message=self.context.status_msg,
            estimated=self.context.estimated_size,
            percentage=(self.context.done_size / float(self.context.estimated_size) * 100)
        )

    def cmd_abort(self, args):
        """
        Abort current backup if there is any or return error.
        """
        if not self.context.active:
            self.respond(status="ERROR", msg="No backup is currently pending")
            return

        self.context.backup_thread.stop = True
   
class BackupWorker(threading.Thread):
    def __init__(self, context, backup):
        super(BackupWorker, self).__init__()
        self.context = context
        self.backup = backup
        self.stop = False

    def create_manifest(self):
        try:
            with open(VERSIONFILE) as v:
                build = v.read().strip()
        except:
            build = 'UNKNOWN'

        manifest = {
            'build': build,
            'created-at': time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            'with-data': self.context.backup_data,
            'compression': self.context.compressed
        }

        return json.dumps(manifest, indent=4) + '\n'

    def name_backup(self, time):
        return 'freenas-backup-{:%Y%m%d-%H%M%S}'.format(time);

    def describe_disk(self, diskname):
        disk = Disk.objects.filter(disk_name=diskname).first()
        return {
            'name': diskname,
            'serial': disk.disk_serial,
            'size': disk.disk_size
        }

    def create_volumes_metadata(self):
        volumes = dict()
        nf = notifier.notifier()

        for v in Volume.objects.all():
            if v.vol_fstype == 'ZFS':
                pool = nf.zpool_parse(v.vol_name)
                vol = {
                    "guid": v.vol_guid,
                    "encryptkey": v.vol_encryptkey,
                    "fstype": v.vol_fstype,
                    "with-data": self.context.backup_data and v.vol_fstype == 'ZFS',
                    "data-vdevs": [],
                    "cache-vdevs": [],
                    "spares-vdevs": [],
                    "logs-vdevs": []
                }

                for catname in ('data', 'cache', 'spares', 'logs'):
                    category = getattr(pool, catname)
                    if category is None:
                        continue

                    for i in category:
                        vol['{}-vdevs'.format(catname)].append({
                            'name': i.name,
                            'type': i.type,
                            'disks': [self.describe_disk(d.disk) for d in i]
                        })


                vol['datasets'] = []
                for dname, dset in v.get_datasets(include_root=True).items():
                    opts = nf.zfs_get_options(dname)
                    vol['datasets'].append({
                        'name': dname,
                        'compression': opts['compression']
                    })

                vol['zvols'] = []
                for zname, zvol in v.get_zvols().items():
                     vol['zvols'].append({
                        'name': zname,
                        'size': zvol['volsize'],
                        'compression': zvol['compression']
                    })

                volumes[v.vol_name] = vol

        return json.dumps(volumes, indent=4) + '\n'

    def fail(self, reason):
        self.context.status_msg = reason
        self.context.failed = True
        self.backup.bak_failed = True
        self.backup.bak_status = reason
        self.backup.save()
        os.unlink(self.temp_db)

        self.context.failed_msg = 'FATAL: {}'.format(reason)

        if self.context.shutdown is not None:
            self.context.shutdown()

    def run(self):
        self.context.active = True
        self.context.status_msg = 'Preparing backup...'
        log.info('Starting backup thread')
        log.debug('Remote host address: %s', self.context.hostport)
        log.debug('Remote username: %s', self.context.username)
        log.debug('Remote directory: %s', self.context.remote_directory)

        # Copy database to temporary directory
        self.temp_db = tempfile.mktemp(suffix='backup')
        shutil.copyfile(DATABASEFILE, self.temp_db)

        self.context.estimated_size += os.path.getsize(self.temp_db)

        log.debug('Database estimated size: %dKB', self.context.estimated_size / 1024)

        # Register backup in database
        self.backup.bak_destination = self.context.hostport
        self.backup.bak_started_at = datetime.datetime.now()
        self.backup.bak_worker_pid = os.getpid()
        self.backup.save()

        # Connect to remote system
        try:
            session = open_ssh_connection(
                self.context.hostport,
                self.context.username,
                self.context.password,
                self.context.use_key)
        except Exception as err:
            self.fail(str(err))
            return

        log.debug('Connected to remote host')
        dest_dir = self.name_backup(self.backup.bak_started_at)

        try:
            sftp = sftp_client.SFTPClient.from_transport(session)
            sftp.chdir(self.context.remote_directory)
        except:
            self.fail('Cannot open destination directory')
            return

        try:
            sftp.mkdir(dest_dir)
            sftp.chdir(dest_dir)
            sftp.open('.pending', 'wx').close()
        except IOError:
            self.fail('Cannot create backup directory')
            return

        log.debug('Backup directory: %s', dest_dir)

        try:
            f = sftp.open('manifest.json', 'wx')
            f.write(self.create_manifest())
            f.close()

            log.debug('Transferred manifest file')

            f = sftp.open('volumes.json', 'wx')
            f.write(self.create_volumes_metadata())
            f.close()

            log.debug('Transferred volumes definition')

            sftp.put(self.temp_db, 'freenas-v1.db')

            log.debug('Transferred database')
        except IOError:
            self.fail('Cannot write backup data')
            return

        if self.context.backup_data:
            snapshot_timestamp = '{:%Y%m%d-%H%M%S}'.format(datetime.datetime.now())
            # Create snapshots
            for i in Volume.objects.filter(vol_fstype='ZFS'):
                self.context.status_msg = 'Creating snapshot of volume {}'.format(i.vol_name)
                proc = subprocess.check_call(['zfs', 'snapshot', '-r', i.vol_name + '@' + snapshot_timestamp])

            # Estimate data size
            for i in Volume.objects.filter(vol_fstype='ZFS'):
                self.context.status_msg = 'Estimating data size for volume {}'.format(i.vol_name)
                output = subprocess.check_output(["zfs", "send", "-RPvn", i.vol_name + '@' + snapshot_timestamp], stderr=subprocess.STDOUT)
                match = re.search(re.compile(r'size\s+(\d+)', re.MULTILINE), output)
                size = int(match.group(1))
                self.context.estimated_size += size

            log.debug('Estimated total size: %sKB', self.context.estimated_size / 1024)

            sftp.mkdir('volumes')
            sftp.chdir('volumes')

            # Backup actual data
            for i in Volume.objects.filter(vol_fstype='ZFS'):
                proc = subprocess.Popen(['zfs', 'send', '-R', i.vol_name + '@' + snapshot_timestamp], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

                if self.context.compressed:
                    out = sftp.open('{}.zfs'.format(i.vol_name), 'wx')
                    sink = gzip.GzipFile(fileobj=out, mode='wb')
                else:
                    sink = sftp.open('{}.zfs'.format(i.vol_name), 'wx')

                self.context.status_msg = 'Backing up ZFS volume {}'.format(i.vol_name)

                while True:
                    if self.stop:
                        # Abort backup
                        self.fail('Aborted by user')
                        return

                    buffer = proc.stdout.read(BUFSIZE)
                    if len(buffer) == 0:
                        break

                    sink.write(buffer)
                    self.context.done_size += len(buffer)

                sink.close()
                if self.context.compressed:
                    out.close()

                proc.wait()

        self.context.status_msg = 'Done'
        self.backup.bak_finished = 'Done'
        self.backup.bak_finished = True
        self.backup.bak_finished_at = datetime.datetime.now()
        self.backup.save()
        os.unlink(self.temp_db)

        if self.context.shutdown is not None:
            self.context.shutdown()

class RestoreWorker(object):
    class BackupEntry:
        def __init__(self, name, created_at, build, with_data, compressed):
            self.name = name
            self.created_at = created_at
            self.build = build
            self.with_data = with_data
            self.compressed = compressed

    class RestoreThread(threading.Thread):
        def __init__(self, context, volumes, sftp, compressed):
            super(RestoreWorker.RestoreThread, self).__init__()
            self.context = context
            self.volumes = volumes
            self.sftp = sftp
            self.compressed = compressed

        def fail(self, message):
            self.context.failed_msg = 'FATAL: {}'.format(message)

        def run(self):
            # Calculate size
            for name, i in self.volumes.items():
                if i['fstype'] == 'ZFS':
                    try:
                        self.context.estimated_size += self.sftp.stat(os.path.join('volumes', name + '.zfs')).st_size
                    except IOError as err:
                        self.fail('Unable to estimate size of volume {}: {}'.format(name, err.strerror))
                        return

            # Do actual restore
            for name, i in self.volumes.items():
                self.context.status_msg = 'Reconstructing data of volume {}'.format(name)
                oldcwd = os.getcwd()

                if i['fstype'] == 'ZFS':
                    try:
                        if self.compressed:
                            inp = self.sftp.open(os.path.join('volumes', name + '.zfs'), 'r')
                            source = gzip.GzipFile(fileobj=inp, mode='r')
                        else:
                            source = self.sftp.open(os.path.join('volumes', name + '.zfs'), 'r')

                        sink = subprocess.Popen(['zfs', 'receive', '-F', name], stdin=subprocess.PIPE)

                        while True:
                            buffer = source.read(BUFSIZE)
                            if len(buffer) == 0:
                                break

                            sink.stdin.write(buffer)
                            self.context.done_size += len(buffer)
                    except IOError as err:
                        self.fail('Unable to restore volume {}: {}'.format(name, err.strerror))
                        return

                os.chdir(oldcwd)

    def __init__(self, context):
        self.context = context
        self.notifier = notifier.notifier()
        self.used_disks = []

    def fail(self, message):
        self.context.failed_msg = 'FATAL: {}'.format(message)

    def guess_disk(self, diskdata):
        # 1. try to look up disk by serial
        if len(diskdata['serial']) > 0:
            try:
                disk = Disk.objects.get(disk_serial=diskdata['serial'])
                return (disk.disk_name, 'serial')
            except Disk.DoesNotExist:
                pass

        # 2. try to look up for disk with same mediasize
        try:
            disk = Disk.objects.exclude(disk_name__in = self.used_disks).filter(disk_size=diskdata['size']).first()
            return (disk.disk_name, 'size')
        except Disk.DoesNotExist:
            pass

        # 3. try to look up for disk with similar size (at most 5% larger but not smaller)
        reqsize = int(diskdata['size'])
        for i in Disk.objects.exclude(disk_name__in = self.used_disks):
            actsize = int(i.disk_size)
            if actsize >= reqsize and actsize < (reqsize * 1.05):
                return (i.disk_name, 'fuzzy')

        return (None, 'no match')

    def reconstruct_zfs_volume(self, name, volume):
        print('Attempting to reconstruct volume {}:'.format(name))

        vol = Volume.objects.get(vol_guid=volume['guid'])
        if vol is None:
            print('    Volume not found in database - volumes.json and database not in sync')
            return False

        # 1. Check if we already imported that volume
        if vol.status != 'UNKNOWN':
            print '    Pool already imported and online'
            return True

        # 2. Try to import pool
        if self.notifier.zfs_import(vol.vol_name, vol.vol_guid):
            print '    Imported existing volume'
            return True

        # 3. Try to recreate pool
        grps = {}
        for catname in ('data', 'cache', 'spares', 'logs'):
            groups = volume['{}-vdevs'.format(catname)]
            for group in groups:
                print('    Group: {}'.format(group['name']))

                grp = {
                    'type': group['type'],
                    'disks': []
                }

                for vdev in group['disks']:
                    sys.stdout.write('\t{} [{}]: '.format(vdev['name'], humanize_size(vdev['size'])))
                    disk, match = self.guess_disk(vdev)
                    if disk is None:
                        print('not found')
                        print('    Reconstruction of volume {} aborted due to lack of matching device'.format(name))
                        return False

                    print('found {} [{} match]'.format(disk, match))
                    self.used_disks.append(disk)
                    grp['disks'].append(disk)

                grps[group['name']] = grp

        self.notifier.init('volume', vol, groups=grps)

        # 3. Recreate datasets
        print('    Recreating datasets:')
        for dset in volume['datasets']:
            print('\t{}'.format(dset['name']))
            self.notifier.create_zfs_dataset(dset['name'])

        # 4. Recreate zvols
        if len(volume['zvols']) > 0:
            print('    Recreating zvols:')
            for zvol in volume['zvols']:
                print('\t{} [{}]'.format(zvol['name'], humanize_size(zvol['size'])))
                self.notifier.create_zfs_vol(zvol['name'], zvol['size'])

        return True

    def reconstruct_ufs_volume(self, name, volume):
        print('Attempting to reconstruct volume {}:'.format(name))

        vol = Volume.objects.get(vol_name=name)
        if vol is None:
            print('    Volume not found in database - volumes.json and database not in sync')
            return False

        self.notifier.init('volume', vol, groups={'root': volume['devs']})
        return True

    def reconstruct_volumes(self, volumes):
        nf = notifier.notifier()
        for name, i in volumes.items():
            if i['fstype'] == 'ZFS':
                self.reconstruct_zfs_volume(name, i)

    def print_backup_details(self, backup):
        print('    Directory name: {}'.format(backup.name))
        print('    Created at: {}'.format(backup.created_at))
        print('    Created using {}'.format(backup.build))
        print('    Backup {}'.format('contains data' if backup.with_data else 'doesn\'t contain data'))

        if backup.with_data and backup.compressed:
            print('    Backup data is compressed')

        my_version = open(VERSIONFILE, 'r').read().strip()

        if my_version != backup.build:
            print('    WARNING: BACKUP CREATED USING DIFFERENT FREENAS VERSION')
            print('    RESTORING FROM THAT BACKUP IS STRONGLY DISCOURAGED')

    def choose_backup(self, sftp):
        backups = []
        for fname in sftp.listdir():
            try:
                if not stat.S_ISDIR(sftp.stat(fname).st_mode):
                    continue
            except IOError:
                continue

            try:
                manifest = sftp.open(os.path.join(fname, 'manifest.json'), 'r')
                data = json.loads(manifest.read())
                manifest.close()
            except IOError:
                continue
            except ValueError:
                continue

            backups.append(self.BackupEntry(fname,
                data['created-at'],
                data['build'],
                data['with-data'],
                data['compression'] if 'compression' in data else False)
            )

        if len(backups) == 0:
            print('No backups found in given directory!')
            return None

        if len(backups) == 1:
            backup = backups[0]
            print('Found single backup in given directory:')
            self.print_backup_details(backup)
            if raw_input('Restore whole FreeNAS installation from that backup? (y/n): ').lower() == 'y':
                return backup
            else:
                return None

        backups.sort(key=lambda x: x.created_at, reverse=True)
        buffer = '    {:<40}{:<24}{:<12}\n'.format('Backup name', 'Backup timestamp', 'With data?')
        for idx, i in enumerate(backups, start=1):
            buffer += '{:>2}. {:<40}{:<24}{:<12}\n'.format(idx, i.name, i.created_at, 'yes' if i.with_data else 'no')

        pydoc.pager(buffer)

        choose = raw_input('Type backup no. to restore or leave field blank to use newest one: ')
        if not choose.strip().isdigit():
            idx = 0
        else:
            idx = int(choose.strip()) - 1

        backup = backups[idx]
        print('Backup details:')
        self.print_backup_details(backup)
        if raw_input('Restore whole FreeNAS installation from that backup? (y/n): ').lower() == 'y':
            return backup
        else:
            return None


    def run(self):
        print("Logging in to remote system...")

        # Connect to remote system
        try:
            session = open_ssh_connection(
                self.context.hostport,
                self.context.username,
                self.context.password,
                self.context.use_key)
        except Exception as err:
            self.fail(err.message)
            return

        except socket.gaierror:
            self.fail('Cannot connect to remote host')
            raise
        except ssh_exception.BadAuthenticationType:
            self.fail('Cannot authenticate')
            raise

        sftp = sftp_client.SFTPClient.from_transport(session)
        sftp.chdir(self.context.remote_directory)
        backup = None

        while backup is None:
            backup = self.choose_backup(sftp)
            if backup is not None:
                break

            if raw_input('Do you want to abort? (y/n):') == 'y':
                return

        try:
            sftp.chdir(backup.name)

            print('Restoring database...')

            # Stop services which might use .system
            if os.path.exists('/var/run/syslog.pid'):
                self.notifier.stop('syslogd')

            if os.path.exists('/var/run/samba/smbd.pid'):
                self.notifier.stop('cifs')

            if os.path.exists('/var/run/collectd.pid'):
                self.notifier.stop('collectd')

            if os.path.exists('/var/run/django.pid'):
                self.notifier.stop('django')

            if os.path.exists('/var/run/nginx.pid'):
                self.notifier.stop('nginx')

            # Restore database
            shutil.move(DBFILE, DBFILE + '.bak')
            sftp.get('freenas-v1.db', DBFILE)

            with open(os.devnull, 'w') as devnull:
                if subprocess.call([
                        '/usr/local/www/freenasUI/manage.py',
                        'migrate',
                        '--merge',
                        '--delete-ghost-migrations'
                    ], stdout=devnull, stderr=devnull) != 0:
                    self.fail('Could not restore database')
                    return

            # Update disk entries
            self.notifier.sync_disks()

            # Download volumes.json
            try:
                f = sftp.open('volumes.json')
                volumes = json.load(f)
            except ValueError:
                self.fail('Invalid volumes.json file')
                return
        except IOError:
            self.fail('Cannot download backup files')
            return

        # Destroy old volumes
        print('Destroying existing volumes (if any)...')
        try:
            pools = subprocess.check_output(['zpool', 'list', '-H', '-o', 'name'])
            for i in pools.split():
                subprocess.call(['zpool', 'destroy', i])
        except subprocess.CalledProcessError:
            # bug in zpool list with -H argument - returns random
            # error code when there are no pools
            pass

        # Remove latest backup entry, since it's the one created
        # when saving backup
        bak = Backup.objects.all().order_by('-bak_started_at').first()
        if not bak.bak_acknowledged:
            bak.delete()

        # Reconstruct volumes
        print('Restoring volumes...')
        self.reconstruct_volumes(volumes)

        # Reconstruct data
        if backup.with_data:
            print('Restoring data...')
            thread = self.RestoreThread(self.context, volumes, sftp, backup.compressed)
            thread.start()

            sys.stdout.write('\n')

            while thread.is_alive():
                time.sleep(0.5)
                if self.context.estimated_size != 0:
                    print_progress(self.context.status_msg,
                        self.context.done_size,
                        round(self.context.done_size / float(self.context.estimated_size), 4))

            thread.join()

        # Reboot system at the end
        self.notifier.restart('system')


class PidFile(object):
    """
    Context manager that locks a pid file.
    Implemented as class not generator because daemon.py is calling __exit__
    with no parameters instead of the None, None, None specified by PEP-343.

    Based on:
    http://code.activestate.com/recipes/
    577911-context-manager-for-a-daemon-pid-file/
    """

    def __init__(self, path):
        self.path = path
        self.pidfile = None

    def __enter__(self):
        self.pidfile = open(self.path, "a+")
        try:
            fcntl.flock(self.pidfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise SystemExit("Already running according to " + self.path)
        self.pidfile.seek(0)
        self.pidfile.truncate()
        self.pidfile.write(str(os.getpid()))
        self.pidfile.flush()
        self.pidfile.seek(0)
        return self.pidfile

    def __exit__(self, *args, **kwargs):
        try:
            if os.path.exists(self.path):
                os.unlink(self.path)
            self.pidfile.close()
        except IOError:
            pass

def split_hostport(str):
    if ':' in str:
        parts = str.split(':')
        return (parts[0], int(parts[1]))
    else:
        return (str, 22)

def open_ssh_connection(hostport, username, password, use_keys):
        try:
            session = transport.Transport(split_hostport(hostport))
            session.start_client()
            session.window_size = 134217727
            session.packetizer.REKEY_BYTES = pow(2, 48)
            session.packetizer.REKEY_PACKETS = pow(2, 48)

            if use_keys:
                if try_key_auth(session, username):
                    return session
                else:
                    raise Exception('Cannot authenticate using keys')

            session.auth_password(username, password)
            return session

        except socket.gaierror as err:
            raise Exception('Connection error: {}'.format(err.strerror))
        except ssh_exception.BadAuthenticationType:
            raise Exception('Cannot authenticate')

def try_key_auth(session, username):
    try:
        key = rsakey.RSAKey.from_private_key_file('/root/.ssh/id_rsa')
        session.auth_publickey(username, key)
        return True
    except ssh_exception.SSHException:
        pass

    try:
        key = dsskey.DSSKey.from_private_key_file('/root/.ssh/id_dsa')
        session.auth_publickey(username, key)
        return True
    except ssh_exception.SSHException:
        pass

    return False

def ask(context, backup=True):
    while True:
        context.hostport = raw_input("Hostname or IP address: ")
        context.username = raw_input("Username: ")
        context.password = raw_input("Password (leave empty to use key authentication): ")
        context.remote_directory = raw_input("Remote directory: ")

        if len(context.password) == 0:
            context.use_key = True

        if backup:
            context.backup_data = raw_input("Backup data? (y/n): ").lower() == 'y'
            print('Backup data {}selected'.format('' if context.backup_data else 'not '))
            context.compressed = raw_input("Compress data? (y/n): ").lower() == 'y'
            print('Compress data {}selected'.format('' if context.compressed else 'not '))

        answer = raw_input('Are these values OK? (y/n/q): ').lower()
        if answer == 'y':
            break

        if answer == 'q':
            sys.exit(0)

def get_terminal_size():
    import fcntl, termios, struct
    h, w, hp, wp = struct.unpack('HHHH',
        fcntl.ioctl(0, termios.TIOCGWINSZ,
        struct.pack('HHHH', 0, 0, 0, 0)))
    return w, h

def sigint_handler(sig, frame):
    print('Aborting...')
    os._exit(1)

def print_progress(message, done, percentage):
    global progress_old_done
    global progress_old_time

    if percentage > 1:
        percentage = 1

    if progress_old_time is None:
        progress_old_time = datetime.datetime.now()

    now = datetime.datetime.now()
    progress_width = get_terminal_size()[0] - 22
    filled_width = int(percentage * progress_width)
    avg_speed = (done - progress_old_done)

    # Erase 2 lines above
    sys.stdout.write('\033[2K\033[A\033[2K\r')
    sys.stdout.write('Status: {}\n'.format(message))
    sys.stdout.write('[{}{}] {}/s {:.2%}'.format(
        '#' * filled_width, '_' * (progress_width - filled_width),
        humanize_size(avg_speed),
        percentage))

    sys.stdout.flush()
    progress_old_done = done
    progress_old_time = datetime.datetime.now()

def backup(argv):
    context = BackupContext()
    ask(context)

    bak = Backup()
    bak.bak_started_at = datetime.datetime.now()
    bak.save()

    context.backup_thread = BackupWorker(context, bak)
    context.backup_thread.start()

    sys.stdout.write('\n')

    while context.backup_thread.is_alive():
        time.sleep(0.5)
        if context.estimated_size != 0:
            print_progress(context.status_msg,
                context.done_size,
                round(context.done_size / float(context.estimated_size), 4))

    sys.stdout.write('\n')

    context.backup_thread.join()
    if context.failed_msg is not None:
        print(context.failed_msg)
        sys.exit(1)

def restore(argv):
    context = BackupContext()
    ask(context, backup=False)
    worker = RestoreWorker(context)
    worker.run()
    sys.stdout.write('\n')

    if context.failed_msg is not None:
        print(context.failed_msg)
        sys.exit(1)


def files_preserve_by_path(*paths):
    from resource import getrlimit, RLIMIT_NOFILE

    wanted=[]
    for path in paths:
        fd = os.open(path, os.O_RDONLY)
        try:
            wanted.append(os.fstat(fd)[1:3])
        finally:
            os.close(fd)

    def fd_wanted(fd):
        try:
            return os.fstat(fd)[1:3] in wanted
        except OSError:
            return False

    fd_max = getrlimit(RLIMIT_NOFILE)[1]
    return [ fd for fd in xrange(fd_max) if fd_wanted(fd) ]


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', action='store_true', help='Interactive mode')
    parser.add_argument('-r', action='store_true', help='Restore from backup')
    args = parser.parse_args()

    if args.r and args.i:
        # Launch restore in interactive mode
        signal.signal(signal.SIGINT, sigint_handler)
        return restore(argv)

    if args.i:
        # Launch backup in interactive mode
        signal.signal(signal.SIGINT, sigint_handler)
        return backup(argv)

    pidfile = PidFile('/var/run/backupd.pid')

    context = daemon.DaemonContext(
        working_directory='/root',
        umask=0o002,
        pidfile=pidfile,
        stdout=sys.stdout,
        stdin=sys.stdin,
        stderr=sys.stderr,
        files_preserve=files_preserve_by_path('/dev/urandom')
    )

    with context:
        main_loop()

if __name__ == '__main__':
    main(sys.argv[1:])

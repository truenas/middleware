from bsd import geom
from middlewared.schema import accepts, Bool, Dict, Str
from middlewared.service import job, private, CallError, Service
from middlewared.utils import Popen

import aiohttp
import asyncio
import enum
import json
import os
import shutil
import subprocess
import textwrap

UPLOAD_LOCATION = '/var/tmp/firmware'
UPLOAD_LABEL = 'updatemdu'


def parse_train_name(name):
    split = name.split('-')
    version = split[1].split('.')
    branch = split[2]

    return [int(v) if v.isdigit() else v for v in version] + [branch]


class CompareTrainsResult(enum.Enum):
    MAJOR_DOWNGRADE = "MAJOR_DOWNGRADE"
    MAJOR_UPGRADE = "MAJOR_UPGRADE"
    MINOR_DOWNGRADE = "MINOR_DOWNGRADE"
    MINOR_UPGRADE = "MINOR_UPGRADE"
    NIGHTLY_DOWNGRADE = "NIGHTLY_DOWNGRADE"
    NIGHTLY_UPGRADE = "NIGHTLY_UPGRADE"


def compare_trains(t1, t2):
    v1 = parse_train_name(t1)
    v2 = parse_train_name(t2)

    if v1[0] != v2[0]:
        if v1[0] > v2[0]:
            return CompareTrainsResult.MAJOR_DOWNGRADE
        else:
            return CompareTrainsResult.MAJOR_UPGRADE

    branch1 = v1[-1].lower().replace("-sdk", "")
    branch2 = v2[-1].lower().replace("-sdk", "")
    if branch1 != branch2:
        if branch2 == "nightlies":
            return CompareTrainsResult.NIGHTLY_UPGRADE
        elif branch1 == "nightlies":
            return CompareTrainsResult.NIGHTLY_DOWNGRADE

    if (
        # [11, "STABLE"] -> [11, 1, "STABLE"]
        not isinstance(v1[1], int) and isinstance(v2[1], int) or
        # [11, 1, "STABLE"] -> [11, 2, "STABLE"]
        isinstance(v1[1], int) and isinstance(v2[1], int) and v1[1] < v2[1]
    ):
        return CompareTrainsResult.MINOR_UPGRADE

    if (
        isinstance(v1[1], int) and isinstance(v2[1], int) and v1[1] > v2[1] or
        not isinstance(v2[1], int) and v1[1] > 0
    ):
        return CompareTrainsResult.MINOR_DOWNGRADE


class SysupException(Exception):
    pass


class Sysup(object):

    async def __aenter__(self):
        self.proc = await Popen(
            ['sysup', '-websocket'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        #try:
        #    line = await asyncio.wait_for(self.proc.stdout.readline(), 10)
        #except asyncio.TimeoutError:
        #    raise SysupException('Timed out waiting update process to initialize websocket.')
        asyncio.ensure_future(self._log_proc())
        try:
            self.session = aiohttp.ClientSession()
            self.ws = await self.session.ws_connect('tcp://localhost:8134/ws')
        except Exception:
            self.proc.kill()
            raise
        return self

    async def _log_proc(self):
        while True:
            try:
                line = await self.proc.stdout.readline()
                self.logger.debug(f'sysup: {line}')
            except Exception:
                break

    async def _send_receive(self, method, data=None, end_method=None, on_info=None):
        payload = {'method': method}
        if data:
            payload.update(data)
        await self.ws.send_str(json.dumps(payload))

        while True:
            msg = await self.ws.receive()
            if msg.type != aiohttp.WSMsgType.TEXT:
                raise SysupException('Unexpected response')

            data = json.loads(msg.data)
            if data['method'] == 'fatal':
                raise SysupException(data['info'])

            if on_info and data['method'] == 'info':
                await on_info(data['info'])

            if data['method'] == (end_method or method):
                break
        return data

    async def get_trains(self):
        return await self._send_receive('listtrains')

    async def set_train(self, name):
        return await self._send_receive('settrain', data={'Train': name})

    async def check(self):
        return await self._send_receive('check')

    async def update(self, filepath=None, cachedir=None, on_info=None):
        data = {}
        if cachedir:
            data['cachedir'] = cachedir
        return await self._send_receive('update', end_method='shutdown', data=data, on_info=on_info)

    async def __aexit__(self, typ, value, traceback):
        await self.ws.close()
        await self.session.close()
        self.proc.kill()
        if typ is not None:
            raise


class UpdateService(Service):

    @accepts()
    async def get_trains(self):
        """
        Returns available trains dict and the currently configured train as well as the
        train of currently booted environment.
        """
        try:
            async with Sysup() as sysup:
                sysuptrains = await sysup.get_trains()
        except SysupException as e:
            raise CallError(str(e))

        data = await self.middleware.call('datastore.config', 'system.update')

        current = selected = None
        trains = {}
        for train in sysuptrains['trains']:
            if not selected and data['upd_train'] == train['name']:
                selected = train['name']
            if train['current']:
                current = train['name']
            trains[train['name']] = {
                'description': train['description'],
                'sequence': train['version'],
            }
        return {
            'trains': trains,
            'current': current,
            'selected': selected,
        }

    @accepts(Str('name'))
    async def set_train(self, name):
        """
        Set the current train to `train`.
        """
        try:
            async with Sysup() as sysup:
                await sysup.set_train(name)
        except SysupException as e:
            raise CallError(str(e))

        data = await self.middleware.call('datastore.config', 'system.update')
        if data['upd_train'] != name:
            await self.middleware.call('datastore.update', 'system.update', data['id'], {
                'upd_train': name,
            })
        return True

    @accepts(Dict(
        'update-check-available',
        Str('train', required=False),
        required=False,
    ))
    async def check_available(self, attrs):
        """
        Checks if there is an update available from update server.

        status:
          - REBOOT_REQUIRED: an update has already been applied
          - AVAILABLE: an update is available
          - UNAVAILABLE: no update available

        .. examples(websocket)::

          Check available update using default train:

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "update.check_available"
            }
        """

        try:
            applied = await self.middleware.call('cache.get', 'update.applied')
        except Exception:
            applied = False
        if applied is True:
            return {'status': 'REBOOT_REQUIRED'}

        train = attrs.get('train')
        if train:
            await self.middleware.call('update.set_train', train)

        try:
            async with Sysup() as sysup:
                check = await sysup.check()
        except SysupException as e:
            raise CallError(str(e))

        if not check['updates']:
            return {'status': 'UNAVAILABLE'}

        changes = []
        version = None
        for i in (check['details']['update'] or []):
            if i['name'] == 'freenas':
                version = i['NewVersion']
            changes.append({
                'operation': 'upgrade',
                'old': {'name': i['name'], 'version': i['OldVersion']},
                'new': {'name': i['name'], 'version': i['NewVersion']},
            })

        for i in (check['details']['new'] or []):
            changes.append({
                'operation': 'install',
                'old': None,
                'new': {'name': i['name'], 'version': i['Version']},
            })

        for i in (check['details']['delete'] or []):
            changes.append({
                'operation': 'delete',
                'old': {'name': i['name'], 'version': i['Version']},
                'new': None,
            })

        data = {
            'status': 'AVAILABLE',
            'changes': changes,
            'notice': None,
            'notes': None,
            'changelog': None,
            'version': version,
        }

        return data

    @accepts(Str('path', null=True, default=None))
    async def get_pending(self, path=None):
        """
        Gets a list of packages already downloaded and ready to be applied.
        Each entry of the lists consists of type of operation and name of it, e.g.

          {
            "operation": "upgrade",
            "name": "baseos-11.0 -> baseos-11.1"
          }
        """
        if path is None:
            path = await self.middleware.call('update.get_update_location')

        data = []
        return data

    @accepts(Dict(
        'update',
        Str('train', required=False),
        Bool('reboot', default=False),
        required=False,
    ))
    @job(lock='update')
    async def update(self, job, attrs):
        """
        Downloads (if not already in cache) and apply an update.
        """

        if attrs.get('train'):
            await self.middleware.call('update.set_train', attrs['train'])

        trains = await self.middleware.call('update.get_trains')
        train = trains['selected']
        try:
            result = compare_trains(trains['current'], train)
        except Exception:
            self.logger.warning("Failed to compare trains %r and %r", trains['current'], train, exc_info=True)
        else:
            errors = {
                CompareTrainsResult.NIGHTLY_DOWNGRADE: textwrap.dedent("""\
                    You're not allowed to change away from the nightly train, it is considered a downgrade.
                    If you have an existing boot environment that uses that train, boot into it in order to upgrade
                    that train.
                """),
                CompareTrainsResult.MINOR_DOWNGRADE: textwrap.dedent("""\
                    Changing minor version is considered a downgrade, thus not a supported operation.
                    If you have an existing boot environment that uses that train, boot into it in order to upgrade
                    that train.
                """),
                CompareTrainsResult.MAJOR_DOWNGRADE: textwrap.dedent("""\
                    Changing major version is considered a downgrade, thus not a supported operation.
                    If you have an existing boot environment that uses that train, boot into it in order to upgrade
                    that train.
                """),
            }
            if result in errors:
                raise CallError(errors[result])

        location = await self.middleware.call('update.get_update_location')

        async def on_info(info):
            job.set_progress(None, info)

        try:
            async with Sysup() as sysup:
                await sysup.update(cachedir=location, on_info=on_info)
        except SysupException as e:
            raise CallError(str(e))

        await self.middleware.call('cache.put', 'update.applied', True)

        if attrs.get('reboot'):
            await self.middleware.call('system.reboot', {'delay': 10})
        return True

    @accepts()
    @job(lock='updatedownload')
    async def download(self, job):
        """
        Download updates using selected train.
        """
        train = self.middleware.call_sync('update.get_trains')['selected']
        location = self.middleware.call_sync('update.get_update_location')

        self.middleware.call_sync('alert.alert_source_clear_run', 'HasUpdate')

        return True

    @accepts(Str('path'))
    @job(lock='updatemanual', process=True)
    async def manual(self, job, path):
        """
        Apply manual update of file `path`.
        """

        async def on_info(info):
            job.set_progress(None, info)

        try:
            async with Sysup() as sysup:
                await sysup.update(filepath=path, on_info=on_info)
        except SysupException as e:
            raise CallError(str(e))

        if path.startswith(UPLOAD_LOCATION):
            await self.middleware.call('update.destroy_upload_location')

    @accepts(Dict(
        'updatefile',
        Str('destination', null=True),
    ))
    @job(lock='updatemanual', pipes=['input'])
    async def file(self, job, options):
        """
        Updates the system using the uploaded .tar file.

        Use null `destination` to create a temporary location.
        """

        dest = options.get('destination')

        if not dest:
            try:
                await self.middleware.call('update.create_upload_location')
                dest = '/var/tmp/firmware'
            except Exception as e:
                raise CallError(str(e))
        elif not dest.startswith('/mnt/'):
            raise CallError('Destination must reside within a pool')

        if not os.path.isdir(dest):
            raise CallError('Destination is not a directory')

        destfile = os.path.join(dest, 'manualupdate.tar')

        try:
            job.set_progress(10, 'Writing uploaded file to disk')
            with open(destfile, 'wb') as f:
                await self.middleware.run_in_thread(
                    shutil.copyfileobj, job.pipes.input.r, f, 1048576,
                )

            async def on_info(info):
                job.set_progress(None, info)

            async with Sysup() as sysup:
                await sysup.update(filepath=destfile, on_info=on_info)

            job.set_progress(95, 'Cleaning up')

        except SysupException as e:
            raise CallError(str(e))
        finally:
            if os.path.exists(destfile):
                os.unlink(destfile)

        if dest == '/var/tmp/firmware':
            await self.middleware.call('update.destroy_upload_location')

        job.set_progress(100, 'Update completed')

    @private
    async def get_update_location(self):
        updatepath = '/update'
        return updatepath
        updateds = 'freenas-boot/update'
        ds = await self.middleware.call('zfs.dataset.query', [('id', '=', updateds)])
        if not ds:
            await self.middleware.call('zfs.dataset.create', {
                'name': updateds,
                'properties': {
                    'mountpoint': '/update',
                }
            })
            await self.middleware.call('zfs.dataset.mount', updateds)

    @private
    def create_upload_location(self):
        geom.scan()
        klass_label = geom.class_by_name('LABEL')
        prov = klass_label.xml.find(
            f'.//provider[name = "label/{UPLOAD_LABEL}"]/../consumer/provider'
        )
        if prov is None:
            cp = subprocess.run(
                ['mdconfig', '-a', '-t', 'swap', '-s', '2800m'],
                text=True, capture_output=True, check=False,
            )
            if cp.returncode != 0:
                raise CallError(f'Could not create memory device: {cp.stderr}')
            mddev = cp.stdout.strip()

            subprocess.run(['glabel', 'create', UPLOAD_LABEL, mddev], capture_output=True, check=False)

            cp = subprocess.run(
                ['newfs', f'/dev/label/{UPLOAD_LABEL}'],
                text=True, capture_output=True, check=False,
            )
            if cp.returncode != 0:
                raise CallError(f'Could not create temporary filesystem: {cp.stderr}')

            shutil.rmtree(UPLOAD_LOCATION, ignore_errors=True)
            os.makedirs(UPLOAD_LOCATION)

            cp = subprocess.run(
                ['mount', f'/dev/label/{UPLOAD_LABEL}', UPLOAD_LOCATION],
                text=True, capture_output=True, check=False,
            )
            if cp.returncode != 0:
                raise CallError(f'Could not mount temporary filesystem: {cp.stderr}')

        shutil.chown(UPLOAD_LOCATION, 'www', 'www')
        os.chmod(UPLOAD_LOCATION, 0o755)

    @private
    def destroy_upload_location(self):
        geom.scan()
        klass_label = geom.class_by_name('LABEL')
        prov = klass_label.xml.find(
            f'.//provider[name = "label/{UPLOAD_LABEL}"]/../consumer/provider'
        )
        if prov is None:
            return
        klass_md = geom.class_by_name('MD')
        prov = klass_md.xml.find(f'.//provider[@id = "{prov.attrib["ref"]}"]/name')
        if prov is None:
            return

        mddev = prov.text

        subprocess.run(
            ['umount', f'/dev/label/{UPLOAD_LABEL}'], capture_output=True, check=False,
        )
        cp = subprocess.run(
            ['mdconfig', '-d', '-u', mddev],
            text=True, capture_output=True, check=False,
        )
        if cp.returncode != 0:
            raise CallError(f'Could not destroy memory device: {cp.stderr}')

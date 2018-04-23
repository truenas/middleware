import asyncio
import errno
import logging
from datetime import datetime, time
import os
import re
import subprocess
import sysctl

import bsd

from middlewared.job import JobProgressBuffer
from middlewared.schema import accepts, Bool, Cron, Dict, Int, List, Patch, Str
from middlewared.service import (
    ConfigService, filterable, item_method, job, private, CallError, CRUDService, ValidationErrors
)
from middlewared.utils import Popen, filter_list, run
from middlewared.validators import Range, Time

logger = logging.getLogger(__name__)


def _none(x):
    if x is None:
        return 'none'
    return x


def _null(x):
    if x == 'none':
        return None
    return x


async def is_mounted(middleware, path):
    mounted = await middleware.run_in_thread(bsd.getmntinfo)
    return any(fs.dest == path for fs in mounted)


async def mount(device, path, fs_type, fs_options, options):
    options = options or []

    if isinstance(device, str):
        device = device.encode("utf-8")

    if isinstance(path, str):
        path = path.encode("utf-8")

    if fs_type == "msdosfs":
        options.append("large")

    executable = "/sbin/mount"
    arguments = []

    if fs_type == "ntfs":
        executable = "/usr/local/bin/ntfs-3g"
    elif fs_type == "msdosfs" and fs_options:
        executable = "/sbin/mount_msdosfs"
        if "locale" in fs_options:
            arguments.extend(["-L", fs_options["locale"]])
        arguments.extend(sum([["-o", option] for option in options], []))
        options = []
    else:
        arguments.extend(["-t", fs_type])

    if options:
        arguments.extend(["-o", ",".join(options)])

    proc = await Popen(
        [executable] + arguments + [device, path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf8",
    )
    output = await proc.communicate()

    if proc.returncode != 0:
        logger.debug("Mount failed (%s): %s", proc.returncode, output)
        raise ValueError("Mount failed (exit code {0}):\n{1}{2}" .format(
            proc.returncode,
            output[0].decode("utf-8"),
            output[1].decode("utf-8"),
        ))
    else:
        return True


class PoolResilverService(ConfigService):

    class Config:
        namespace = 'pool.resilver'
        datastore = 'storage.resilver'
        datastore_extend = 'pool.resilver.resilver_extend'

    async def resilver_extend(self, data):
        data['begin'] = data['begin'].strftime('%H:%M')
        data['end'] = data['end'].strftime('%H:%M')
        data['weekday'] = [int(v) for v in data['weekday'].split(',')]
        return data

    async def validate_fields_and_update(self, data, schema):
        verrors = ValidationErrors()

        begin = data.get('begin')
        if begin:
            data['begin'] = time(int(begin.split(':')[0]), int(begin.split(':')[1]))

        end = data.get('end')
        if end:
            data['end'] = time(int(end.split(':')[0]), int(end.split(':')[1]))

        weekdays = data.get('weekday')
        if weekdays:
            if len([day for day in weekdays if day not in range(1, 8)]) > 0:
                verrors.add(
                    f'{schema}.weekday',
                    'The week days should be in range of 1-7 inclusive'
                )
            else:
                data['weekday'] = ','.join([str(day) for day in weekdays])

        return verrors, data

    @accepts(
        Dict(
            'pool_resilver',
            Str('begin', validators=[Time()]),
            Str('end', validators=[Time()]),
            Bool('enabled'),
            List('weekday', items=[Int('weekday')])
        )
    )
    async def do_update(self, data):
        config = await self.config()
        original_config = config.copy()
        config.update(data)

        verrors, new_config = await self.validate_fields_and_update(config, 'pool_resilver_update')
        if verrors:
            raise verrors

        # before checking if any changes have been made, original_config needs to be mapped to new_config
        original_config['weekday'] = ','.join([str(day) for day in original_config['weekday']])
        original_config['begin'] = time(*(int(value) for value in original_config['begin'].split(':')))
        original_config['end'] = time(*(int(value) for value in original_config['end'].split(':')))
        if len(set(original_config.items()) ^ set(new_config.items())) > 0:
            # data has changed
            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                new_config['id'],
                new_config
            )

            await self.middleware.call('service.restart', 'cron', {'onetime': False})
            await self.middleware.call('pool.configure_resilver_priority')

        return await self.config()


class KernelModuleContextManager:
    def __init__(self, module):
        self.module = module

    async def __aenter__(self):
        if self.module is not None:
            if not await self.module_loaded():
                await run('kldload', self.module, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if not await self.module_loaded():
                    raise Exception('Kernel module %r failed to load', self.module)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.module is not None:
            try:
                await run('kldunload', self.module, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    async def module_loaded(self):
        return (await run('kldstat', '-n', self.module, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)).returncode == 0


class MountFsContextManager:
    def __init__(self, middleware, device, path, *args, **kwargs):
        self.middleware = middleware
        self.device = device
        self.path = path
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        await mount(self.device, self.path, *self.args, **self.kwargs)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if await is_mounted(self.middleware, self.path):
            await self.middleware.run_in_thread(bsd.unmount, self.path)


class PoolService(CRUDService):

    GELI_KEYPATH = '/data/geli'

    @filterable
    async def query(self, filters=None, options=None):
        filters = filters or []
        options = options or {}
        options['extend'] = 'pool.pool_extend'
        options['prefix'] = 'vol_'
        return await self.middleware.call('datastore.query', 'storage.volume', filters, options)

    @private
    async def pool_extend(self, pool):
        pool.pop('fstype', None)

        """
        If pool is encrypted we need to check if the pool is imported
        or if all geli providers exist.
        """
        try:
            zpool = (await self.middleware.call('zfs.pool.query', [('id', '=', pool['name'])]))[0]
        except Exception:
            zpool = None

        if zpool:
            pool['status'] = zpool['status']
            pool['scan'] = zpool['scan']
        else:
            pool.update({
                'status': 'OFFLINE',
                'scan': None,
            })

        if pool['encrypt'] > 0:
            if zpool:
                pool['is_decrypted'] = True
            else:
                decrypted = True
                for ed in await self.middleware.call('datastore.query', 'storage.encrypteddisk', [('encrypted_volume', '=', pool['id'])]):
                    if not os.path.exists(f'/dev/{ed["encrypted_provider"]}.eli'):
                        decrypted = False
                        break
                pool['is_decrypted'] = decrypted
        else:
            pool['is_decrypted'] = True
        return pool

    @item_method
    @accepts(Int('id', required=False))
    async def get_disks(self, oid=None):
        """
        Get all disks in use by pools.
        If `id` is provided only the disks from the given pool `id` will be returned.
        """
        filters = []
        if oid:
            filters.append(('id', '=', oid))
        for pool in await self.query(filters):
            if pool['is_decrypted']:
                async for i in await self.middleware.call('zfs.pool.get_disks', pool['name']):
                    yield i
            else:
                for encrypted_disk in await self.middleware.call('datastore.query', 'storage.encrypteddisk',
                                                                 [('encrypted_volume', '=', pool['id'])]):
                    disk = {k[len("disk_"):]: v for k, v in encrypted_disk["encrypted_disk"].items()}
                    name = await self.middleware.call("disk.get_name", disk)
                    if os.path.exists(os.path.join("/dev", name)):
                        yield name

    @item_method
    @accepts(Int('id'))
    async def download_encryption_key(self, oid):
        """
        Download encryption key for a given pool `id`.
        """
        pool = await self.query([('id', '=', oid)], {'get': True})
        if not pool['encryptkey']:
            return None

        job_id, url = await self.middleware.call(
            'core.download',
            'filesystem.get',
            [os.path.join(self.GELI_KEYPATH, f"{pool['encryptkey']}.key")],
            'geli.key'
        )
        return url

    @private
    def configure_resilver_priority(self):
        """
        Configure resilver priority based on user selected off-peak hours.
        """
        resilver = self.middleware.call_sync('datastore.config', 'storage.resilver')

        if not resilver['enabled'] or not resilver['weekday']:
            return

        higher_prio = False
        weekdays = map(lambda x: int(x), resilver['weekday'].split(','))
        now = datetime.now()
        now_t = now.time()
        # end overlaps the day
        if resilver['begin'] > resilver['end']:
            if now.isoweekday() in weekdays and now_t >= resilver['begin']:
                higher_prio = True
            else:
                lastweekday = now.isoweekday() - 1
                if lastweekday == 0:
                    lastweekday = 7
                if lastweekday in weekdays and now_t < resilver['end']:
                    higher_prio = True
        # end does not overlap the day
        else:
            if now.isoweekday() in weekdays and now_t >= resilver['begin'] and now_t < resilver['end']:
                higher_prio = True

        if higher_prio:
            resilver_delay = 0
            resilver_min_time_ms = 9000
            scan_idle = 0
        else:
            resilver_delay = 2
            resilver_min_time_ms = 3000
            scan_idle = 50

        sysctl.filter('vfs.zfs.resilver_delay')[0].value = resilver_delay
        sysctl.filter('vfs.zfs.resilver_min_time_ms')[0].value = resilver_min_time_ms
        sysctl.filter('vfs.zfs.scan_idle')[0].value = scan_idle

    @accepts()
    async def import_find(self):
        """
        Get a list of pools available for import with the following details:
        name, guid, status, hostname.
        """

        existing_guids = [i['guid'] for i in await self.middleware.call('pool.query')]

        for pool in await self.middleware.call('zfs.pool.find_import'):
            if pool['status'] == 'UNAVAIL':
                continue
            # Exclude pools with same guid as existing pools (in database)
            # It could be the pool is in the database but was exported/detached for some reason
            # See #6808
            if pool['guid'] in existing_guids:
                continue
            entry = {}
            for i in ('name', 'guid', 'status', 'hostname'):
                entry[i] = pool[i]
            yield entry

    @accepts(Dict(
        'pool_import',
        Str('guid', required=True),
        Str('name'),
        Str('passphrase', private=True),
        List('devices', items=[Str('device')]),
    ))
    @job(lock='import_pool', pipes=['input'], check_pipes=False)
    async def import_pool(self, job, data):
        """
        Import a pool.

        Errors:
            ENOENT - Pool not found
        """

        pool = None
        for p in await self.middleware.call('zfs.pool.find_import'):
            if p['guid'] == data['guid']:
                pool = p
                break
        if pool is None:
            raise CallError(f'Pool with guid "{data["guid"]}" not found', errno.ENOENT)

        if data['devices']:
            job.check_pipe("input")
            args = [job.pipes.input.r, data['passphrase'], data['devices']]
        else:
            args = []

        await self.middleware.call('notifier.volume_import', data.get('name') or pool['name'], data['guid'], *args)
        return True

    @accepts(Str('volume'), Str('fs_type'), Dict('fs_options', additional_attrs=True), Str('dst_path'))
    @job(lock=lambda args: 'volume_import', logs=True)
    async def import_disk(self, job, volume, fs_type, fs_options, dst_path):
        job.set_progress(None, description="Mounting")

        src = os.path.join('/var/run/importcopy/tmpdir', os.path.relpath(volume, '/'))

        if os.path.exists(src):
            os.rmdir(src)

        try:
            os.makedirs(src)

            async with KernelModuleContextManager({"msdosfs": "msdosfs_iconv",
                                                   "ntfs": "fuse"}.get(fs_type)):
                async with MountFsContextManager(self.middleware, volume, src, fs_type, fs_options, ["ro"]):
                    job.set_progress(None, description="Importing")

                    line = [
                        '/usr/local/bin/rsync',
                        '--info=progress2',
                        '--modify-window=1',
                        '-rltvh',
                        '--no-perms',
                        src + '/',
                        dst_path
                    ]
                    rsync_proc = await Popen(
                        line, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0, preexec_fn=os.setsid,
                    )
                    try:
                        progress_buffer = JobProgressBuffer(job)
                        while True:
                            line = await rsync_proc.stdout.readline()
                            job.logs_fd.write(line)
                            if line:
                                try:
                                    line = line.decode("utf-8", "ignore").strip()
                                    bits = re.split("\s+", line)
                                    if len(bits) == 6 and bits[1].endswith("%") and bits[1][:-1].isdigit():
                                        progress_buffer.set_progress(int(bits[1][:-1]))
                                    elif not line.endswith('/'):
                                        if (
                                            line not in ['sending incremental file list'] and
                                            'xfr#' not in line
                                        ):
                                            progress_buffer.set_progress(None, extra=line)
                                except Exception:
                                    logger.warning('Parsing error in rsync task', exc_info=True)
                            else:
                                break

                        progress_buffer.flush()
                        await rsync_proc.wait()
                        if rsync_proc.returncode != 0:
                            raise Exception("rsync failed with exit code %r" % rsync_proc.returncode)
                    except asyncio.CancelledError:
                        rsync_proc.kill()
                        raise

                    job.set_progress(100, description="Done", extra="")
        finally:
            os.rmdir(src)

    @accepts()
    def import_disk_msdosfs_locales(self):
        return [
            locale.strip()
            for locale in subprocess.check_output(["locale", "-a"], encoding="utf-8").split("\n")
            if locale.strip()
        ]

    """
    These methods are hacks for old UI which supports only one volume import at a time
    """

    dismissed_import_disk_jobs = set()

    @private
    async def get_current_import_disk_job(self):
        import_jobs = await self.middleware.call('core.get_jobs', [('method', '=', 'pool.import_disk')])
        not_dismissed_import_jobs = [job for job in import_jobs if job["id"] not in self.dismissed_import_disk_jobs]
        if not_dismissed_import_jobs:
            return not_dismissed_import_jobs[0]

    @private
    async def dismiss_current_import_disk_job(self):
        current_import_job = await self.get_current_import_disk_job()
        if current_import_job:
            self.dismissed_import_disk_jobs.add(current_import_job["id"])


class PoolDatasetService(CRUDService):

    class Config:
        namespace = 'pool.dataset'

    @filterable
    def query(self, filters, options):
        # Otimization for cases in which they can be filtered at zfs.dataset.query
        zfsfilters = []
        for f in filters:
            if len(f) == 3:
                if f[0] in ('id', 'name', 'pool', 'type'):
                    zfsfilters.append(f)
        datasets = self.middleware.call_sync('zfs.dataset.query', zfsfilters, None)
        return filter_list(self.__transform(datasets), filters, options)

    def __transform(self, datasets):
        """
        We need to transform the data zfs gives us to make it consistent/user-friendly,
        making it match whatever pool.dataset.{create,update} uses as input.
        """

        def transform(dataset):
            for orig_name, new_name, method in (
                ('org.freenas:description', 'comments', None),
                ('dedup', 'deduplication', str.upper),
                ('atime', None, str.upper),
                ('casesensitivity', None, str.upper),
                ('exec', None, str.upper),
                ('sync', None, str.upper),
                ('compression', None, str.upper),
                ('origin', None, None),
                ('quota', None, _null),
                ('refquota', None, _null),
                ('reservation', None, _null),
                ('refreservation', None, _null),
                ('copies', None, None),
                ('snapdir', None, str.upper),
                ('readonly', None, str.upper),
                ('recordsize', None, None),
                ('sparse', None, None),
                ('volsize', None, None),
                ('volblocksize', None, None),
            ):
                if orig_name not in dataset['properties']:
                    continue
                i = new_name or orig_name
                dataset[i] = dataset['properties'][orig_name]
                if method:
                    dataset[i]['value'] = method(dataset[i]['value'])
            del dataset['properties']

            if dataset['type'] == 'FILESYSTEM':
                dataset['share_type'] = self.middleware.call_sync(
                    'notifier.get_dataset_share_type', dataset['name'],
                ).upper()
            else:
                dataset['share_type'] = None

            rv = []
            for child in dataset['children']:
                rv.append(transform(child))
            dataset['children'] = rv
            return dataset

        rv = []
        for dataset in datasets:
            rv.append(transform(dataset))
        return rv

    @accepts(Dict(
        'pool_dataset_create',
        Str('name', required=True),
        Str('type', enum=['FILESYSTEM', 'VOLUME'], default='FILESYSTEM'),
        Int('volsize'),
        Str('volblocksize', enum=[
            '512', '1K', '2K', '4K', '8K', '16K', '32K', '64K', '128K',
        ]),
        Bool('sparse'),
        Str('comments'),
        Str('sync', enum=[
            'STANDARD', 'ALWAYS', 'DISABLED',
        ]),
        Str('compression', enum=[
            'OFF', 'LZ4', 'GZIP-1', 'GZIP-6', 'GZIP-9', 'ZLE', 'LZJB',
        ]),
        Str('atime', enum=['ON', 'OFF']),
        Str('exec', enum=['ON', 'OFF']),
        Int('quota'),
        Int('refquota'),
        Int('reservation'),
        Int('refreservation'),
        Int('copies'),
        Str('snapdir', enum=['VISIBLE', 'HIDDEN']),
        Str('deduplication', enum=['ON', 'VERIFY', 'OFF']),
        Str('readonly', enum=['ON', 'OFF']),
        Str('recordsize', enum=[
            '512', '1K', '2K', '4K', '8K', '16K', '32K', '64K', '128K', '256K', '512K', '1024K',
        ]),
        Str('casesensitivity', enum=['SENSITIVE', 'INSENSITIVE', 'MIXED']),
        Str('share_type', enum=['UNIX', 'WINDOWS', 'MAC']),
        register=True,
    ))
    async def do_create(self, data):
        """
        Creates a dataset/zvol.

        `volsize` is required for type=VOLUME and is supposed to be a multiple of the block size.
        """

        verrors = ValidationErrors()
        await self.__common_validation(verrors, 'pool_dataset_create', data, 'CREATE')
        if verrors:
            raise verrors

        props = {}
        for i, real_name, transform in (
            ('atime', None, str.lower),
            ('casesensitivity', None, str.lower),
            ('comments', 'org.freenas:description', None),
            ('compression', None, str.lower),
            ('copies', None, lambda x: str(x)),
            ('deduplication', 'dedup', str.lower),
            ('exec', None, str.lower),
            ('quota', None, _none),
            ('readonly', None, str.lower),
            ('recordsize', None, None),
            ('refquota', None, _none),
            ('refreservation', None, _none),
            ('reservation', None, _none),
            ('snapdir', None, str.lower),
            ('sparse', None, None),
            ('sync', None, str.lower),
            ('volblocksize', None, None),
            ('volsize', None, lambda x: str(x)),
        ):
            if i not in data:
                continue
            name = real_name or i
            props[name] = data[i] if not transform else transform(data[i])

        await self.middleware.call('zfs.dataset.create', {
            'name': data['name'],
            'type': data['type'],
            'properties': props,
        })

        if data['type'] == 'FILESYSTEM':
            await self.middleware.call(
                'notifier.change_dataset_share_type', data['name'], data.get('share_type', 'UNIX').lower()
            )

        await self.middleware.call('zfs.dataset.mount', data['name'])

    def _add_inherit(name):
        def add(attr):
            attr.enum.append('INHERIT')
        return {'name': name, 'method': add}

    @accepts(Str('id'), Patch(
        'pool_dataset_create', 'pool_dataset_update',
        ('rm', {'name': 'name'}),
        ('rm', {'name': 'type'}),
        ('rm', {'name': 'casesensitivity'}),  # Its a readonly attribute
        ('rm', {'name': 'sparse'}),  # Create time only attribute
        ('rm', {'name': 'volblocksize'}),  # Create time only attribute
        ('edit', _add_inherit('atime')),
        ('edit', _add_inherit('exec')),
        ('edit', _add_inherit('sync')),
        ('edit', _add_inherit('compression')),
        ('edit', _add_inherit('deduplication')),
        ('edit', _add_inherit('readonly')),
        ('edit', _add_inherit('recordsize')),
        ('edit', _add_inherit('snapdir')),
        ('attr', {'update': True}),
    ))
    async def do_update(self, id, data):
        """
        Updates a dataset/zvol `id`.
        """

        verrors = ValidationErrors()

        dataset = await self.middleware.call('pool.dataset.query', [('id', '=', id)])
        if not dataset:
            verrors.add('id', f'{id} does not exist', errno.ENOENT)
        else:
            data['type'] = dataset[0]['type']
            await self.__common_validation(verrors, 'pool_dataset_update', data, 'UPDATE')
        if verrors:
            raise verrors

        props = {}
        for i, real_name, transform, inheritable in (
            ('atime', None, str.lower, True),
            ('comments', 'org.freenas:description', None, False),
            ('sync', None, str.lower, True),
            ('compression', None, str.lower, True),
            ('deduplication', 'dedup', str.lower, True),
            ('exec', None, str.lower, True),
            ('quota', None, _none, False),
            ('refquota', None, _none, False),
            ('reservation', None, _none, False),
            ('refreservation', None, _none, False),
            ('copies', None, None, False),
            ('snapdir', None, str.lower, True),
            ('readonly', None, str.lower, True),
            ('recordsize', None, None, True),
            ('volsize', None, lambda x: str(x), False),
        ):
            if i not in data:
                continue
            name = real_name or i
            if inheritable and data[i] == 'INHERIT':
                props[name] = {'source': 'INHERIT'}
            else:
                props[name] = {'value': data[i] if not transform else transform(data[i])}

        rv = await self.middleware.call('zfs.dataset.update', id, {'properties': props})

        if data['type'] == 'FILESYSTEM' and 'share_type' in data:
            await self.middleware.call(
                'notifier.change_dataset_share_type', id, data['share_type'].lower()
            )

        return rv

    async def __common_validation(self, verrors, schema, data, mode):
        assert mode in ('CREATE', 'UPDATE')

        if data['type'] == 'FILESYSTEM':
            for i in ('sparse', 'volsize', 'volblocksize'):
                if i in data:
                    verrors.add(f'{schema}.{i}', 'This field is not valid for FILESYSTEM')
        elif data['type'] == 'VOLUME':
            if mode == 'CREATE' and 'volsize' not in data:
                verrors.add(f'{schema}.volsize', 'This field is required for VOLUME')

            for i in (
                'atime', 'casesensitivity', 'quota', 'refquota', 'recordsize', 'share_type',
            ):
                if i in data:
                    verrors.add(f'{schema}.{i}', 'This field is not valid for VOLUME')

    @accepts(Str('id'))
    async def do_delete(self, id):
        return await self.middleware.call('zfs.dataset.delete', id)

    @item_method
    @accepts(Str('id'))
    async def promote(self, id):
        """
        Promote the cloned dataset `id`
        """
        dataset = await self.middleware.call('zfs.dataset.query', [('id', '=', id)])
        if not dataset:
            raise CallError(f'Dataset "{id}" does not exist.', errno.ENOENT)
        if not dataset[0]['properties']['origin']['value']:
            raise CallError('Only cloned datasets can be promoted.', errno.EBADMSG)
        return await self.middleware.call('zfs.dataset.promote', id)


class PoolScrubService(CRUDService):

    class Config:
        datastore = 'storage.scrub'
        datastore_extend = 'pool.scrub.pool_scrub_extend'
        datastore_prefix = 'scrub_'
        namespace = 'pool.scrub'

    @private
    async def pool_scrub_extend(self, data):
        data['pool'] = data.pop('volume')
        data['pool'] = data['pool']['id']
        Cron.convert_db_format_to_schedule(data)
        return data

    @private
    async def validate_data(self, data, schema):
        verrors = ValidationErrors()

        pool_pk = data.get('pool')
        if pool_pk:
            pool_obj = await self.middleware.call(
                'datastore.query',
                'storage.volume',
                [('id', '=', pool_pk)]
            )

            if len(pool_obj) == 0:
                verrors.add(
                    f'{schema}.pool',
                    'The specified volume does not exist'
                )
            elif (
                    'id' not in data.keys() or
                    (
                        'id' in data.keys() and
                        'original_pool_id' in data.keys() and
                        pool_pk != data['original_pool_id']
                    )
            ):
                scrub_obj = await self.query(filters=[('volume_id', '=', pool_pk)])
                if len(scrub_obj) != 0:
                    verrors.add(
                        f'{schema}.pool',
                        'A scrub with this pool already exists'
                    )

        return verrors, data

    @accepts(
        Dict(
            'pool_scrub_create',
            Int('pool', validators=[Range(min=1)], required=True),
            Int('threshold', validators=[Range(min=0)]),
            Str('description'),
            Cron('schedule'),
            Bool('enabled'),
            register=True
        )
    )
    async def do_create(self, data):
        verrors, data = await self.validate_data(data, 'pool_scrub_create')

        if verrors:
            raise verrors

        data['volume'] = data.pop('pool')
        Cron.convert_schedule_to_db_format(data)

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call(
            'service.restart',
            'cron',
            {'onetime': False}
        )

        return await self.query(filters=[('id', '=', data['id'])], options={'get': True})

    @accepts(
        Int('id', validators=[Range(min=1)]),
        Patch('pool_scrub_create', 'pool_scrub_update', ('attr', {'update': True}))
    )
    async def do_update(self, id, data):
        task_data = await self.query(filters=[('id', '=', id)], options={'get': True})
        original_data = task_data.copy()
        task_data['original_pool_id'] = original_data['pool']
        task_data.update(data)
        verrors, task_data = await self.validate_data(task_data, 'pool_scrub_update')

        if verrors:
            raise verrors

        task_data.pop('original_pool_id')
        Cron.convert_schedule_to_db_format(task_data)
        Cron.convert_schedule_to_db_format(original_data)

        if len(set(task_data.items()) ^ set(original_data.items())) > 0:

            task_data['volume'] = task_data.pop('pool')

            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                id,
                task_data,
                {'prefix': self._config.datastore_prefix}
            )

            await self.middleware.call(
                'service.restart',
                'cron',
                {'onetime': False}
            )

        return await self.query(filters=[('id', '=', id)], options={'get': True})

    @accepts(
        Int('id')
    )
    async def do_delete(self, id):
        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

        await self.middleware.call(
            'service.restart',
            'cron',
            {'onetime': False}
        )
        return response


def setup(middleware):
    asyncio.ensure_future(middleware.call('pool.configure_resilver_priority'))

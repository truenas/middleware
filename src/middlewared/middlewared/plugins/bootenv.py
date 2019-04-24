from middlewared.schema import Bool, Dict, Str, accepts
from middlewared.service import (
    CallError, CRUDService, ValidationErrors, filterable, item_method, job
)
from middlewared.utils import Popen, filter_list, run
from middlewared.validators import Match

from datetime import datetime

import errno
import subprocess


RE_BE_NAME = r'^[^/ *\'"?@!#$%^&()+=~<>;\\]+$'


class BootEnvService(CRUDService):

    @filterable
    def query(self, filters=None, options=None):
        """
        Query all Boot Environments with `query-filters` and `query-options`.
        """
        results = []

        cp = subprocess.run(['beadm', 'list', '-H'], capture_output=True, text=True)
        for line in cp.stdout.strip().split('\n'):
            fields = line.split('\t')
            name = fields[0]
            if len(fields) > 5 and fields[5] != '-':
                name = fields[5]
            be = {
                'id': fields[0],
                'realname': fields[0],
                'name': name,
                'active': fields[1],
                'mountpoint': fields[2],
                'space': fields[3],
                'created': datetime.strptime(fields[4], '%Y-%m-%d %H:%M'),
                'keep': None,
                'rawspace': None
            }

            ds = self.middleware.call_sync('zfs.dataset.query', [
                ('id', '=', f'freenas-boot/ROOT/{fields[0]}'),
            ])
            if ds:
                ds = ds[0]
                rawspace = 0
                for i in ('usedbydataset', 'usedbyrefreservation', 'usedbysnapshots'):
                    rawspace += ds['properties'][i]['parsed']
                origin = ds['properties']['origin']['parsed']
                if '@' in origin:
                    snap = self.middleware.call_sync('zfs.snapshot.query', [('id', '=', origin)])
                    if snap:
                        snap = snap[0]
                        rawspace += snap['properties']['used']['parsed']
                if 'beadm:keep' in ds['properties']:
                    if ds['properties']['beadm:keep']['value'] == 'True':
                        be['keep'] = True
                    elif ds['properties']['beadm:keep']['value'] == 'False':
                        be['keep'] = False
            results.append(be)
        return filter_list(results, filters, options)

    @item_method
    @accepts(Str('id'))
    def activate(self, oid):
        """
        Activates boot environment `id`.
        """
        try:
            subprocess.run(['beadm', 'activate', oid], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as cpe:
            raise CallError(f'Failed to activate BE: {cpe.stdout.strip()}')
        else:
            return True

    @item_method
    @accepts(
        Str('id'),
        Dict(
            'attributes',
            Bool('keep', default=False),
        )
    )
    def set_attribute(self, oid, attrs):
        """
        Sets attributes boot environment `id`.

        Currently only `keep` attribute is allowed.
        """
        dsname = f'freenas-boot/ROOT/{oid}'
        ds = self.middleware.call_sync('zfs.dataset.query', [('id', '=', dsname)])
        if not ds:
            raise CallError(f'BE {oid!r} does not exist.', errno.ENOENT)
        ds = ds[0]
        self.middleware.call_sync('zfs.dataset.update', dsname, {
            'properties': {'beadm:keep': {'value': str(attrs['keep'])}},
        })
        return True

    @accepts(Dict(
        'bootenv_create',
        Str('name', required=True, validators=[Match(RE_BE_NAME)]),
        Str('source'),
    ))
    async def do_create(self, data):
        """
        Create a new boot environment using `name`.

        If a new boot environment is desired which is a clone of another boot environment, `source` can be passed.
        Then, a new boot environment of `name` is created using boot environment `source` by cloning it.

        Ensure that `name` and `source` are valid boot environment names.
        """
        verrors = ValidationErrors()
        await self._clean_be_name(verrors, 'bootenv_create', data['name'])
        verrors.check()

        args = ['beadm', 'create']
        source = data.get('source')
        if source:
            args += ['-e', source]
        args.append(data['name'])
        try:
            await run(args, encoding='utf8', check=True)
        except subprocess.CalledProcessError as cpe:
            raise CallError(f'Failed to create boot environment: {cpe.stdout}')
        return data['name']

    @accepts(Str('id'), Dict(
        'bootenv_update',
        Str('name', required=True, validators=[Match(RE_BE_NAME)]),
    ))
    async def do_update(self, oid, data):
        """
        Update `id` boot environment name with a new provided valid `name`.
        """
        be = await self._get_instance(oid)

        verrors = ValidationErrors()
        await self._clean_be_name(verrors, 'bootenv_update', data['name'])
        verrors.check()

        try:
            await run('beadm', 'rename', oid, data['name'], encoding='utf8', check=True)
        except subprocess.CalledProcessError as cpe:
            raise CallError(f'Failed to update boot environment: {cpe.stdout}')
        return data['name']

    async def _clean_be_name(self, verrors, schema, name):
        beadm_names = (await (await Popen(
            "beadm list | awk '{print $7}'",
            shell=True,
            encoding='utf8',
        )).communicate())[0].split('\n')
        if name in filter(None, beadm_names):
            verrors.add(f'{schema}.name', f'The name "{name}" already exists', errno.EEXIST)

    @accepts(Str('id'))
    @job(lock=lambda args: f'bootenv_delete_{args[0]}')
    async def do_delete(self, job, oid):
        """
        Delete `id` boot environment. This removes the clone from the system.
        """
        be = await self._get_instance(oid)
        try:
            await run('beadm', 'destroy', '-F', be['id'], encoding='utf8', check=True)
        except subprocess.CalledProcessError as cpe:
            raise CallError(f'Failed to delete boot environment: {cpe.stdout}')
        return True

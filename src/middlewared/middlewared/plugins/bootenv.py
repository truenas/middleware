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
        datasets_origins = [
            d['properties']['origin']['parsed']
            for d in self.middleware.call_sync('zfs.dataset.query')
        ]
        boot_pool = self.middleware.call_sync('boot.pool_name')
        for line in cp.stdout.strip().split('\n'):
            fields = line.split('\t')
            name = fields[0]
            if len(fields) > 5 and fields[5] != '-':
                name = fields[5]
            be = {
                'id': name,
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
                ('id', '=', rf'{boot_pool}/ROOT/{fields[0]}'),
            ], {'extra': {'snapshots': True}})
            if ds:
                ds = ds[0]
                snapshot = None
                origin = ds['properties']['origin']['parsed']
                if '@' in origin:
                    snapshot = self.middleware.call_sync('zfs.snapshot.query', [('id', '=', origin)])
                    if snapshot:
                        snapshot = snapshot[0]
                if 'beadm:keep' in ds['properties']:
                    if ds['properties']['beadm:keep']['value'] == 'True':
                        be['keep'] = True
                    elif ds['properties']['beadm:keep']['value'] == 'False':
                        be['keep'] = False

                # When a BE is deleted, following actions happen
                # 1) It's descendants ( if any ) are promoted once
                # 2) BE is deleted
                # 3) Filesystems dependent on BE's origin are promoted
                # 4) Origin is deleted
                #
                # Now we would like to find out the space which will be freed when a BE is removed.
                # We classify a BE as of being 2 types,
                # 1) BE without descendants
                # 2) BE with descendants
                #
                # For (1), space freed is "usedbydataset" property and space freed by it's "origin".
                # For (2), space freed is "usedbydataset" property and space freed by it's "origin" but this cannot
                # actively determined because all the descendants are promoted once for this BE and at the end origin
                # of current BE would be determined by last descendant promoted. So we ignore this for now and rely
                # only on the space it is currently consuming as a best effort to predict.
                # There is also "usedbysnaps" property, for that we will retrieve all snapshots of the dataset,
                # find if any of them do not have a dataset cloned, that space will also be freed when we delete
                # this dataset. And we will also factor in the space consumed by children.

                be['rawspace'] = ds['properties']['usedbydataset']['parsed'] + ds[
                    'properties']['usedbychildren']['parsed']

                children = False
                for snap in ds['snapshots']:
                    if snap['name'] not in datasets_origins:
                        be['rawspace'] += snap['properties']['used']['parsed']
                    else:
                        children = True

                if snapshot and not children:
                    # This indicates the current BE is a leaf and it is safe to add the BE's origin
                    # space to the space freed when it is deleted.
                    be['rawspace'] += snapshot['properties']['used']['parsed']

                if be['rawspace'] < 1024:
                    be['space'] = f'{be["rawspace"]}B'
                elif 1024 <= be['rawspace'] < 1048576:
                    be['space'] = f'{be["rawspace"] / 1024}K'
                elif 1048576 <= be['rawspace'] < 1073741824:
                    be['space'] = f'{be["rawspace"] / 1048576}M'
                elif 1073741824 <= be['rawspace'] < 1099511627776:
                    be['space'] = f'{be["rawspace"] / 1073741824}G'
                elif 1099511627776 <= be['rawspace'] < 1125899906842624:
                    be['space'] = f'{be["rawspace"] / 1099511627776}T'
                elif 1125899906842624 <= be['rawspace'] < 1152921504606846976:
                    be['space'] = f'{be["rawspace"] / 1125899906842624}P'
                elif 1152921504606846976 <= be['rawspace'] < 1152921504606846976:
                    be['space'] = f'{be["rawspace"] / 1152921504606846976}E'
                else:
                    be['space'] = f'{be["rawspace"] / 1152921504606846976}Z'

                be['space'] = f'{round(float(be["space"][:-1]), 2)}{be["space"][-1]}'

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
    async def set_attribute(self, oid, attrs):
        """
        Sets attributes boot environment `id`.

        Currently only `keep` attribute is allowed.
        """
        boot_pool = await self.middleware.call('boot.pool_name')
        boot_env = await self.get_instance(oid)
        dsname = f'{boot_pool}/ROOT/{boot_env["realname"]}'
        ds = await self.middleware.call('zfs.dataset.query', [('id', '=', dsname)])
        if not ds:
            raise CallError(f'BE {oid!r} does not exist.', errno.ENOENT)
        await self.middleware.call('zfs.dataset.update', dsname, {
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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )).communicate())[0].decode().split('\n')
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

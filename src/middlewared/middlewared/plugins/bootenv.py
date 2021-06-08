from middlewared.schema import accepts, Bool, Datetime, Dict, Int, returns, Str
from middlewared.service import (
    CallError, CRUDService, ValidationErrors, filterable, item_method, job
)
from middlewared.utils import filter_list, osc, Popen, run
from middlewared.validators import Match

from datetime import datetime

import errno
import os
import subprocess


RE_BE_NAME = r'^[^/ *\'"?@!#$%^&()+=~<>;\\]+$'


class BootEnvService(CRUDService):

    class Config:
        datastore_primary_key_type = 'string'
        cli_namespace = 'system.bootenv'

    BE_TOOL = 'zectl' if osc.IS_LINUX else 'beadm'
    ENTRY = Dict(
        'bootenv_entry',
        Str('id'),
        Str('realname'),
        Str('name'),
        Str('active'),
        Bool('activated'),
        Bool('can_activate'),
        Str('mountpoint'),
        Str('space'),
        Datetime('created'),
        Bool('keep'),
        Int('rawspace'),
        additional_attrs=True
    )

    @filterable
    def query(self, filters, options):
        """
        Query all Boot Environments with `query-filters` and `query-options`.
        """
        results = []

        cp = subprocess.run([self.BE_TOOL, 'list', '-H'], capture_output=True, text=True)
        datasets_origins = [
            d['properties']['origin']['parsed']
            for d in self.middleware.call_sync('zfs.dataset.query', [], {'extra': {'properties': ['origin']}})
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
                'activated': 'n' in fields[1].lower(),
                'can_activate': False,
                'mountpoint': fields[2],
                'space': None if osc.IS_LINUX else fields[3],
                'created': datetime.strptime(fields[3 if osc.IS_LINUX else 4], '%Y-%m-%d %H:%M'),
                'keep': False,
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
                if f'{self.BE_TOOL}:keep' in ds['properties']:
                    if ds['properties'][f'{self.BE_TOOL}:keep']['value'] == 'True':
                        be['keep'] = True
                    elif ds['properties'][f'{self.BE_TOOL}:keep']['value'] == 'False':
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
                        be['rawspace'] += self.middleware.call_sync(
                            'zfs.snapshot.query', [['id', '=', snap['name']]], {'extra': {'properties': ['used']}}
                        )['properties']['used']['parsed']
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

                if osc.IS_FREEBSD:
                    be['can_activate'] = 'truenas:kernel_version' not in ds['properties']
                if osc.IS_LINUX:
                    be['can_activate'] = (
                        'truenas:kernel_version' in ds['properties'] or
                        'truenas:12' in ds['properties']
                    )

            results.append(be)
        return filter_list(results, filters, options)

    @item_method
    @accepts(Str('id'))
    @returns(Bool('successfully_activated'))
    def activate(self, oid):
        """
        Activates boot environment `id`.
        """
        be = self.middleware.call_sync('bootenv.query', [['id', '=', oid]], {'get': True})
        if not be['can_activate']:
            raise CallError('This BE cannot be activated')

        try:
            subprocess.run([self.BE_TOOL, 'activate', oid], capture_output=True, text=True, check=True)
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
    @returns(Bool('successfully_set_attribute'))
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
            'properties': {f'{self.BE_TOOL}:keep': {'value': str(attrs['keep'])}},
        })
        return True

    @accepts(Dict(
        'bootenv_create',
        Str('name', required=True, validators=[Match(RE_BE_NAME)]),
        Str('source'),
    ))
    @returns(Str('bootenv_name'))
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

        args = [self.BE_TOOL, 'create']
        source = data.get('source')
        if source:
            args += [
                '-e', os.path.join(
                    await self.middleware.call('boot.pool_name'), 'ROOT', source
                ) if osc.IS_LINUX else source
            ]
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
    @returns(Str('bootenv_name'))
    async def do_update(self, oid, data):
        """
        Update `id` boot environment name with a new provided valid `name`.
        """
        await self._get_instance(oid)

        verrors = ValidationErrors()
        await self._clean_be_name(verrors, 'bootenv_update', data['name'])
        verrors.check()

        try:
            await run(self.BE_TOOL, 'rename', oid, data['name'], encoding='utf8', check=True)
        except subprocess.CalledProcessError as cpe:
            raise CallError(f'Failed to update boot environment: {cpe.stdout}')
        return data['name']

    async def _clean_be_name(self, verrors, schema, name):
        beadm_names = (await (await Popen(
            f"{self.BE_TOOL} list -H | awk '{{print ${1 if osc.IS_LINUX else 7}}}'",
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
            await run(self.BE_TOOL, 'destroy', '-F', be['id'], encoding='utf8', check=True)
        except subprocess.CalledProcessError as cpe:
            raise CallError(f'Failed to delete boot environment: {cpe.stdout}')
        return True

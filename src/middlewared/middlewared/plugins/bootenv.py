from middlewared.schema import Bool, Dict, Str, accepts
from middlewared.service import (
    CallError, CRUDService, ValidationErrors, filterable, item_method, job
)
from middlewared.utils import filter_list
from middlewared.validators import Match

from datetime import datetime
from freenasOS import Update

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
                'realname': fields[0],
                'name': name,
                'active': fields[1],
                'mountpoint': fields[2],
                'space': fields[3],
                'created': datetime.strptime(fields[4], '%Y-%m-%d %H:%M'),
                'keep': None,
                'rawspace': None
            }

            ds = self.middleware.call_sync('zfs.dataset.query', [('id', '=', fields[0])])
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
                    if ds['properties']['beadm:keep'] == 'True':
                        be['keep'] = True
                    elif ds['properties']['beadm:keep'] == 'False':
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
        clone = Update.FindClone(oid)
        return Update.CloneSetAttr(clone, **attrs)

    @accepts(Dict(
        'bootenv_create',
        Str('name', required=True, validators=[Match(RE_BE_NAME)]),
        Str('source'),
    ))
    def do_create(self, data):
        """
        Create a new boot environment using `name`.

        If a new boot environment is desired which is a clone of another boot environment, `source` can be passed.
        Then, a new boot environment of `name` is created using boot environment `source` by cloning it.

        Ensure that `name` and `source` are valid boot environment names.
        """
        verrors = ValidationErrors()
        self._clean_be_name(verrors, 'bootenv_create', data['name'])
        if verrors:
            raise verrors

        kwargs = {}
        source = data.get('source')
        if source:
            kwargs['bename'] = source
        clone = Update.CreateClone(data['name'], **kwargs)
        if clone is False:
            raise CallError('Failed to create boot environment')
        return data['name']

    @accepts(Str('id'), Dict(
        'bootenv_update',
        Str('name', required=True, validators=[Match(RE_BE_NAME)]),
    ))
    def do_update(self, oid, data):
        """
        Update `id` boot environment name with a new provided valid `name`.
        """

        verrors = ValidationErrors()
        self._clean_be_name(verrors, 'bootenv_update', data['name'])
        if verrors:
            raise verrors

        if not Update.RenameClone(oid, data['name']):
            raise CallError('Failed to update boot environment')
        return data['name']

    def _clean_be_name(self, verrors, schema, name):
        beadm_names = subprocess.Popen(
            "beadm list | awk '{print $7}'",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf8',
        ).communicate()[0].split('\n')
        if name in filter(None, beadm_names):
            verrors.add(f'{schema}.name', f'The name "{name}" already exists', errno.EEXIST)

    @accepts(Str('id'))
    @job(lock=lambda args: f'bootenv_delete_{args[0]}')
    def do_delete(self, job, oid):
        """
        Delete `id` boot environment. This removes the clone from the system.
        """
        return Update.DeleteClone(oid)

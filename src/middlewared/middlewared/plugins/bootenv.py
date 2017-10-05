from middlewared.schema import Bool, Dict, Str, accepts
from middlewared.service import CallError, CRUDService, ValidationErrors, filterable, item_method
from middlewared.utils import filter_list

from freenasOS import Update

import errno
import subprocess


class BootEnvService(CRUDService):

    @filterable
    def query(self, filters=None, options=None):
        results = []
        for clone in Update.ListClones():
            clone['id'] = clone['name']
            results.append(clone)
        return filter_list(results, filters, options)

    @item_method
    @accepts(Str('id'))
    def activate(self, oid):
        """
        Activates boot environment `id`.
        """
        return Update.ActivateClone(oid)

    @item_method
    @accepts(
        Str('id'),
        Dict(
            'attributes',
            Bool('keep'),
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
        Str('name', required=True),
        Str('source'),
    ))
    def do_create(self, data):

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
        Str('name', required=True),
    ))
    def do_update(self, oid, data):

        verrors = ValidationErrors()
        self._clean_be_name(verrors, 'bootenv_update', data['name'])
        if verrors:
            raise verrors

        if not Update.RenameClone(oid, data['name']):
            raise CallError('Failed to update boot environment')
        return data['name']

    def _clean_be_name(self, verrors, schema, name):
        if any(elem in name for elem in "/ *'\"?@!#$%^&()+=~<>;\\"):
            verrors.add(f'{schema}.name', 'Name does not allow spaces and the following characters: /*\'"?@')
        else:
            beadm_names = subprocess.Popen(
                "beadm list | awk '{print $7}'",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf8',
            ).communicate()[0].split('\n')
            if name in filter(None, beadm_names):
                verrors.add(f'{schema}.name', f'The name {name} already exists', errno.EEXIST)

    def do_delete(self, oid):
        return Update.DeleteClone(oid)

from middlewared.schema import Bool, Dict, Str, accepts
from middlewared.service import CallError, CRUDService, filterable, item_method
from middlewared.utils import filter_list

from freenasOS import Update


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
        if not Update.RenameClone(oid, data['name']):
            raise CallError('Failed to update boot environment')
        return data['name']

    def do_delete(self, oid):
        return Update.DeleteClone(oid)

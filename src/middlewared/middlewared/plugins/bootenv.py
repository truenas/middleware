from middlewared.schema import Any, Str, accepts
from middlewared.service import CRUDService, filterable, item_method
from middlewared.utils import filter_list

from freenasOS import Update


class BootEnvService(CRUDService):

    @filterable
    def query(self, filters=None, options=None):
        results = [clone for clone in Update.ListClones()]
        return filter_list(results, filters, options)

    @item_method
    @accepts(Str('id'))
    def activate(self, oid):
        """
        Activates boot environment `id`.
        """
        return Update.ActivateClone(oid)

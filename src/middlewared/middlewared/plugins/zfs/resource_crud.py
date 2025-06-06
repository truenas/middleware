from middlewared.api.current import ZFSResourceEntry
from middlewared.service import CRUDService, filterable_api_method
from middlewared.service.decorators import pass_thread_local_storage

try:
    import truenas_pylibzfs
except ImportError:
    truenas_pylibzfs = None


class ZFSResourceService(CRUDService):
    class Config:
        cli_private = True
        namespace = "zfs.resource"
        entry = ZFSResourceEntry

    @filterable_api_method(item=ZFSResourceEntry)
    @pass_thread_local_storage
    def query(self, tls, filters, options):
        pass

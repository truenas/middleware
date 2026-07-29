from typing import Any

from middlewared.plugins.nfs import NFSProtocol
from middlewared.service import Service, private


class NFSService(Service):

    class Config:
        service = "nfs"
        service_verb = "restart"
        datastore_prefix = "nfs_srv_"
        datastore_extend = 'nfs.nfs_extend'

    @private
    async def sec(self, config: dict[str, Any], has_nfs_principal: bool) -> list[str]:
        if NFSProtocol.NFSv4 in config["protocols"]:
            if config["v4_krb"]:
                return ["krb5", "krb5i", "krb5p"]
            elif has_nfs_principal:
                return ["sys", "krb5", "krb5i", "krb5p"]
            else:
                return ["sys"]

        return []

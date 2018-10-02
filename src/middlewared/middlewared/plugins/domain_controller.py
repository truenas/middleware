import socket

from middlewared.schema import accepts, Dict, Int, Str
from middlewared.service import private, SystemServiceService


class DomainControllerService(SystemServiceService):

    class Config:
        service = "domaincontroller"
        datastore_extend = "domaincontroller.domaincontroller_extend"
        datastore_prefix = "dc_"

    @private
    async def domaincontroller_extend(self, domaincontroller):
        domaincontroller['role'] = domaincontroller['role'].upper()
        return domaincontroller

    @private
    async def domaincontroller_compress(self, domaincontroller):
        domaincontroller['role'] = domaincontroller['role'].lower()
        return domaincontroller

    @accepts(Dict(
        'domaincontroller_update',
        Str('realm'),
        Str('domain'),
        Str('role', enum=["DC"]),
        Str('dns_backend', enum=["SAMBA_INTERNAL", "BIND9_FLATFILE", "BIND9_DLZ", "NONE"]),
        Str('dns_forwarder'),
        Str('forest_level', enum=["2000", "2003", "2008", "2008_R2", "2012", "2012_R2"]),
        Str('passwd', private=True),
        Int('kerberos_realm', null=True),
        update=True
    ))
    async def do_update(self, data):
        old = await self.config()

        new = old.copy()
        if new["kerberos_realm"] is not None:
            new["kerberos_realm"] = new["kerberos_realm"]["id"]
        new.update(data)

        if new["kerberos_realm"] is None:
            hostname = socket.gethostname()
            dc_hostname = f"{hostname}.{new['realm'].lower()}"

            new_realm = {
                "krb_realm": new["realm"].upper(),
                "krb_kdc": dc_hostname,
                "krb_admin_server": dc_hostname,
                "krb_kpasswd_server": dc_hostname,
            }

            realm = await self.middleware.call("datastore.query", "directoryservice.kerberosrealm", [
                ["krb_realm", "=", new["realm"].upper()]
            ])
            if realm:
                await self.middleware.call("datastore.update", "directoryservice.kerberosrealm", realm[0]["id"],
                                           new_realm)
                new["kerberos_realm"] = realm[0]["id"]
            else:
                new["kerberos_realm"] = await self.middleware.call("datastore.insert", "directoryservice.kerberosrealm",
                                                                   new_realm)

        if any(new[k] != old[k] for k in ["realm", "domain"]):
            await self.middleware.call("notifier.samba4", "domain_sentinel_file_remove")

        await self.domaincontroller_compress(new)

        await self._update_service(old, new)

        await self.domaincontroller_extend(new)

        if new["forest_level"] != old["forest_level"]:
            await self.middleware.call("notifier.samba4", "change_forest_level", [new["forest_level"]])

        if new["passwd"] != old["passwd"]:
            await self.middleware.call("notifier.samba4", "set_administrator_password")

        return new

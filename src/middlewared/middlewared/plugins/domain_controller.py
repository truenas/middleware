import socket
import libzfs

from middlewared.schema import accepts, Dict, Int, Str
from middlewared.service import private, SystemServiceService
from middlewared.service_exception import CallError
from middlewared.utils import run


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

    @private
    def is_provisioned(self):
        """
        Presumption that the domain is provisioned is to fail safe.
        Provisioning on top of an existing domain is a destructive process that
        must be avoided.
        """
        provisioned = 'org.ix.activedirectory:provisioned'
        systemdataset = self.middleware.call_sync('systemdataset.config')
        sysvol_path = f"{systemdataset['basename']}/samba4"
        zfs = self.middleware.call_sync('zfs.dataset.query', [('id', '=', sysvol_path)])
        if provisioned not in zfs[0]['properties']:
            return False

        provision_status = zfs[0]['properties']['org.ix.activedirectory:provisioned']

        return False if provision_status['value'] == 'no' else True

    @private
    def set_provisioned(self, value=True):
        systemdataset = self.middleware.call_sync('systemdataset.config')
        sysvol_path = f"{systemdataset['basename']}/samba4"
        ds = {'properties': {'org.ix.activedirectory:provisioned': {'value': 'yes' if value else 'no'}}}
        self.middleware.call_sync('zfs.dataset.do_update', sysvol_path, ds)
        return True

    @private
    async def provision(self, force=False):
        """
        Determine provisioning status based on custom ZFS User Property.
        Re-provisioning on top of an existing domain can have catastrophic results.
        """
        is_already_provisioned = await self.middleware.call('domaincontroller.is_provisioned')
        if is_already_provisioned and not force:
            self.logger.debug("Domain is already provisioned and command does not have 'force' flag. Bypassing.")
            return False

        dc = await self.middleware.call('domaincontroller.config')
        prov = await run([
            "/usr/local/bin/samba-tool",
            'domain', 'provision',
            "--realm", dc['realm'],
            "--domain", dc['domain'],
            "--dns-backend", dc['dns_backend'],
            "--server-role", dc['role'].lower(),
            "--function-level", dc['forest_level'],
            "--option", "vfs objects=dfs_samba4 zfsacl",
            "--use-rfc2307"],
            check=False
        )
        if prov.returncode != 0:
            raise CallError(f"Failed to provision domain: {prov.stderr.decode()}")
        else:
            self.logger.debug(f"Successfully provisioned domain [{dc['domain']}]")
            await self.middleware.call('domaincontroller.set_provisioned', True)
            return True

    @accepts(Dict(
        'domaincontroller_update',
        Str('realm'),
        Str('domain'),
        Str('role', enum=["DC"]),
        Str('dns_backend', enum=["SAMBA_INTERNAL", "BIND9_FLATFILE", "BIND9_DLZ", "NONE"]),
        Str('dns_forwarder'),
        Str('forest_level', enum=["2000", "2003", "2008", "2008_R2", "2012", "2012_R2"]),
        Str('passwd', private=True),
        Int('kerberos_realm', required=False),
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
            await self.middleware.call('domaincontroller.set_provisioned', False)

        await self.domaincontroller_compress(new)

        await self._update_service(old, new)

        await self.domaincontroller_extend(new)

        if new["forest_level"] != old["forest_level"]:
            await self.middleware.call("notifier.samba4", "change_forest_level", [new["forest_level"]])

        if new["passwd"] != old["passwd"]:
            await self.middleware.call("notifier.samba4", "set_administrator_password")

        return new

from middlewared.plugins.smb import SMBCmd
from middlewared.plugins.kerberos import krb5ccache
from middlewared.plugins.activedirectory_.dns import SRV
from middlewared.service import private, job, Service
from middlewared.service_exception import CallError
from middlewared.plugins.directoryservices import DSStatus
from middlewared.utils import run


class ActiveDirectoryService(Service):

    class Config:
        service = "activedirectory"

    @private
    async def net_keytab_add_update_ads(self, service_class):
        if not (await self.middleware.call('nfs.config'))['v4_krb']:
            return False

        cmd = [
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            'ads', 'keytab',
            'add_update_ads', service_class
        ]

        netads = await run(cmd, check=False)
        if netads.returncode != 0:
            raise CallError('failed to set spn entry '
                            f'[{service_class}]: {netads.stdout.decode().strip()}')

        return True

    @private
    async def get_spn_list(self):
        """
        Return list of kerberos SPN entries registered for the server's Active
        Directory computer account. This may not reflect the state of the
        server's current kerberos keytab.
        """
        await self.middleware.call("kerberos.check_ticket")
        spnlist = []
        cmd = [
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            'ads', 'setspn', 'list'
        ]
        netads = await run(cmd, check=False)
        if netads.returncode != 0:
            raise CallError(
                f"Failed to generate SPN list: [{netads.stderr.decode().strip()}]"
            )

        for spn in netads.stdout.decode().splitlines():
            if len(spn.split('/')) != 2:
                continue
            spnlist.append(spn.strip())

        return spnlist

    @private
    async def get_kerberos_servers(self, ad=None):
        """
        This returns at most 3 kerberos servers located in our AD site. This is to optimize
        kerberos configuration for locations where kerberos servers may span the globe and
        have equal DNS weighting. Since a single kerberos server may represent an unacceptable
        single point of failure, fall back to relying on normal DNS queries in this case.
        """
        if ad is None:
            ad = await self.middleware.call('activedirectory.config')

        res = await self.middleware.call(
            'activedirectory.get_n_working_servers',
            ad['domainname'],
            SRV.KERBEROSDOMAINCONTROLLER.name,
            ad['site'],
            3,
            ad['dns_timeout'],
            ad['verbose_logging'],
        )
        if len(res) != 3:
            return None

        return [i['host'] for i in res]

    @private
    async def set_kerberos_servers(self, ad=None):
        if not ad:
            ad = await self.middleware.call_sync('activedirectory.config')
        site_indexed_kerberos_servers = await self.get_kerberos_servers(ad)
        if site_indexed_kerberos_servers:
            await self.middleware.call(
                'kerberos.realm.update',
                ad['kerberos_realm'],
                {'kdc': site_indexed_kerberos_servers}
            )

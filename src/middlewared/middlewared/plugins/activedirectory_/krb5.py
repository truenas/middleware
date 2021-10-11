from middlewared.plugins.smb import SMBCmd
from middlewared.plugins.kerberos import krb5ccache
from middlewared.plugins.activedirectory_.dns import SRV, ActiveDirectory_DNS
from middlewared.schema import accepts
from middlewared.service import private, job, Service
from middlewared.service_exception import CallError
from middlewared.plugins.directoryservices import DSStatus


class ActiveDirectoryService(Service):

    class Config:
        service = "activedirectory"

    @private
    async def _register_dns(self, ad, smb, smb_ha_mode):
        await self.middleware.call('kerberos.check_ticket')
        if not ad['allow_dns_updates'] or smb_ha_mode in ['STANDALONE', 'CLUSTERED']:
            return

        vhost = (await self.middleware.call('network.configuration.config'))['hostname_virtual']
        vips = [i['address'] for i in (await self.middleware.call('interface.ip_in_use', {'static': True}))]
        smb_bind_ips = smb['bindip'] if smb['bindip'] else vips
        to_register = set(vips) & set(smb_bind_ips)
        hostname = f'{vhost}.{ad["domainname"]}'
        cmd = [
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            'ads', 'dns', 'register', hostname
        ]
        cmd.extend(to_register)
        netdns = await run(cmd, check=False)
        if netdns.returncode != 0:
            self.logger.debug("hostname: %s, ips: %s, text: %s",
                              hostname, to_register, netdns.stderr.decode())

    @private
    async def _net_ads_setspn(self, spn_list):
        """
        Only automatically add NFS SPN entries on domain join
        if kerberized nfsv4 is enabled.
        """
        if not (await self.middleware.call('nfs.config'))['v4_krb']:
            return False

        for spn in spn_list:
            cmd = [
                SMBCmd.NET.value,
                '--use-kerberos', 'required',
                '--use-krb5-ccache', krb5ccache.SYSTEM.value,
                'ads', 'setspn',
                'add', spn,
            ]
            netads = await run(cmd, check=False)
            if netads.returncode != 0:
                raise CallError('failed to set spn entry '
                                f'[{spn}]: {netads.stdout.decode().strip()}')

        return True

    @accepts()
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

    @accepts()
    async def change_trust_account_pw(self):
        """
        Force an update of the AD machine account password. This can be used to
        refresh the Kerberos principals in the server's system keytab.
        """
        await self.middleware.call("kerberos.check_ticket")
        workgroup = (await self.middleware.call('smb.config'))['workgroup']
        cmd = [
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            '-w', workgroup,
            'ads', 'changetrustpw',
        ]
        netads = await run(cmd, check=False)
        if netads.returncode != 0:
            raise CallError(
                f"Failed to update trust password: [{netads.stderr.decode().strip()}] "
                f"stdout: [{netads.stdout.decode().strip()}] "
            )

    @private
    @job(lock="spn_manipulation")
    async def add_nfs_spn(self, job, netbiosname, domain, check_health=True, update_keytab=False):
        if check_health:
            ad_state = await self.middleware.call('activedirectory.get_state')
            if ad_state != DSStatus.HEALTHY.name:
                raise CallError("Service Principal Names that are registered in Active Directory "
                                "may only be manipulated when the Active Directory Service is Healthy. "
                                f"Current state is: {ad_state}")

        ok = await self._net_ads_setspn([
            f'nfs/{netbiosname.upper()}.{domain}',
            f'nfs/{netbiosname.upper()}'
        ])
        if not ok:
            return False

        await self.change_trust_account_pw()
        if update_keytab:
            await self.middleware.call('kerberos.keytab.store_samba_keytab')

        return True

    @private
    def get_kerberos_servers(self, ad=None):
        """
        This returns at most 3 kerberos servers located in our AD site. This is to optimize
        kerberos configuration for locations where kerberos servers may span the globe and
        have equal DNS weighting. Since a single kerberos server may represent an unacceptable
        single point of failure, fall back to relying on normal DNS queries in this case.
        """
        if ad is None:
            ad = self.middleware.call_sync('activedirectory.config')

        AD_DNS = ActiveDirectory_DNS(conf=ad, logger=self.logger)
        krb_kdc = AD_DNS.get_n_working_servers(SRV['KERBEROSDOMAINCONTROLLER'], 3)
        krb_admin_server = AD_DNS.get_n_working_servers(SRV['KERBEROS'], 3)
        krb_kpasswd_server = AD_DNS.get_n_working_servers(SRV['KPASSWD'], 3)
        kdc = [i['host'] for i in krb_kdc]
        admin_server = [i['host'] for i in krb_admin_server]
        kpasswd = [i['host'] for i in krb_kpasswd_server]
        for servers in [kdc, admin_server, kpasswd]:
            if len(servers) == 1:
                return None

        return {'kdc': kdc, 'admin_server': admin_server, 'kpasswd_server': kpasswd}

    @private
    def set_kerberos_servers(self, ad=None):
        if not ad:
            ad = self.middleware.call_sync('activedirectory.config')
        site_indexed_kerberos_servers = self.get_kerberos_servers(ad)
        if site_indexed_kerberos_servers:
            self.middleware.call_sync(
                'kerberos.realm.update',
                ad['kerberos_realm'],
                site_indexed_kerberos_servers
            )

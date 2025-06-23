import os
import subprocess
import wbclient

from middlewared.job import Job
from middlewared.plugins.smb_.constants import SMBCmd, SMBPath
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.utils.directoryservices.ad import (
    get_domain_info,
    lookup_dc
)
from middlewared.utils.directoryservices.ad_constants import (
    MAX_KERBEROS_START_TRIES
)
from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.directoryservices.krb5 import (
    gss_dump_cred,
    gss_get_current_cred,
    kerberos_ticket,
)
from middlewared.utils.directoryservices.krb5_constants import krb5ccache, SAMBA_KEYTAB_DIR
from middlewared.utils.directoryservices.krb5_error import (
    KRB5Error,
    KRB5ErrCode,
)
from time import sleep, time


class ADJoinMixin:
    def __ad_has_tkt_principal(self):
        """
        Check whether our current kerberos ticket is based on a kerberos keytab
        or simply user performing kinit with username/password combination.
        """
        cred = gss_get_current_cred(krb5ccache.SYSTEM.value, False)
        if cred is None:
            # No ticket at all
            return False

        cred_info = gss_dump_cred(cred)
        return cred_info['name_type'] == 'KERBEROS_PRINCIPAL'

    def _ad_activate(self, perform_kinit=True) -> None:
        for etc_file in DSType.AD.etc_files:
            self.middleware.call_sync('etc.generate', etc_file)

        self.middleware.call_sync('service.stop', 'idmap')
        self.middleware.call_sync('service.start', 'idmap', {'silent': False})

        # Wait for winbind to come online to provide some time for sysvol replication
        self._ad_wait_wbclient()

        # Reuse existing kerberos ticket if possible. If we're joining AD then it's possible
        # that a call to kerberos.start would fail due to lack of replication.
        if perform_kinit and not self.__ad_has_tkt_principal():
            self.logger.debug('No ticket detected for domain. Starting kerberos service.')
            self._ad_wait_kerberos_start()

    def _ad_wait_wbclient(self) -> None:
        waited = 0
        ctx = wbclient.Ctx()
        while waited <= 60:
            if ctx.domain().domain_info()['online']:
                return

            self.logger.debug('Waiting for domain to come online')
            sleep(1)
            waited += 1

        raise CallError('Timed out while waiting for domain to come online')

    def _ad_wait_kerberos_start(self) -> None:
        """
        After initial AD join we reconfigure kerberos to find KDC via DNS.
        Unfortunately, depending on the AD environment it may take a significant
        amount of time to replicate the new machine account to other domain
        controllers. This means we have a retry loop on starting the kerberos
        service.
        """
        tries = 0
        while tries < MAX_KERBEROS_START_TRIES:
            try:
                self.middleware.call_sync('kerberos.start')
                return
            except KRB5Error as krberr:
                # KRB5KDC_ERR_C_PRINCIPAL_UNKNOWN - account doesn't exist yet
                # KRB5KDC_ERR_CLIENT_REVOKED - account locked (unlock maybe not replicated)
                # KRB5KDC_ERR_PREAUTH_FAILED - bad password (password update not replicated)
                # KRB5_FCC_NOFILE - possible intermittent error due to keychain based credential
                if krberr.krb5_code not in (
                    KRB5ErrCode.KRB5KDC_ERR_C_PRINCIPAL_UNKNOWN,
                    KRB5ErrCode.KRB5KDC_ERR_CLIENT_REVOKED,
                    KRB5ErrCode.KRB5KDC_ERR_PREAUTH_FAILED,
                    KRB5ErrCode.KRB5_FCC_NOFILE,
                ):
                    raise krberr

            sleep(1)
            tries += 1

    def _ad_domain_info(self, domain: str, retry: bool = True) -> dict:
        """
        Use libads from Samba to query information about the specified domain.
        If it is left unspecifed then the value of `domainname` in the
        AD configuration will be used.

        Args:
            domain (str) : name of domain for which to query basic information.
            retry (bool) : if specified then flush out possible caches on failure
                and retry

        Returns:
            See get_domain_info() documentation

        Raises:
            CallError
        """
        try:
            domain_info = get_domain_info(domain)
        except Exception as e:
            if not retry:
                raise e from None

            # samba's gencache may have a stale server affinity entry
            # or stale negative cache results
            self.middleware.call_sync('idmap.gencache.flush')
            domain_info = get_domain_info(domain)

        return domain_info

    def _ad_lookup_dc(self, domain: str, retry: bool = True) -> dict:
        """
        Look up some basic information about the domain controller that
        is currently set in the libads server affinity cache.

        Args:
            domain (str) : name of domain for which to look up domain controller info
            retry (bool) : if specified then flush out possible caches on failure
                and retry

        Returns:
            See lookup_dc() documentation

        Raises:
            CallError
        """
        try:
            dc_info = lookup_dc(domain)
        except Exception as e:
            if not retry:
                raise e from None

            # samba's gencache may have a stale server affinity entry
            # or stale negative cache results
            self.middleware.call_sync('idmap.gencache.flush')
            dc_info = lookup_dc(domain)

        return dc_info

    def _ad_leave(self, job: Job, ds_type: DSType, domain: str):
        """ Delete our computer object from active directory """

        # remove all samba keytabs
        for file in os.listdir(SAMBA_KEYTAB_DIR):
            os.unlink(os.path.join(SAMBA_KEYTAB_DIR, file))

        username = str(gss_get_current_cred(krb5ccache.SYSTEM.value).name)

        netads = subprocess.run([
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            'ads', 'leave',
        ], check=False, capture_output=True)

        if netads.returncode != 0:
            self.logger.warning(
                'Failed to cleanly leave domain. Further action may be required '
                'by an Active Directory administrator: %s', netads.stderr.decode()
            )

    @kerberos_ticket
    def _ad_set_spn(self, netbiosname, domainname):
        def setspn(spn):
            cmd = [
                SMBCmd.NET.value,
                '--use-kerberos', 'required',
                '--use-krb5-ccache', krb5ccache.SYSTEM.value,
                'ads', 'setspn', 'add', spn
            ]

            netads = subprocess.run(cmd, check=False, capture_output=True)
            if netads.returncode != 0:
                self.logger.error("%s: failed to set spn entry: %s", spn,
                                  netads.stdout.decode().strip())

        setspn(f'nfs/{netbiosname.upper()}')
        setspn(f'nfs/{netbiosname.upper()}.{domainname.lower()}')
        self.middleware.call_sync('kerberos.keytab.store_ad_keytab')

    @kerberos_ticket
    def _ad_test_join(self, ds_type: DSType, domain: str):
        """
        Test to see whether we're currently joined to an AD domain.
        """
        netads = subprocess.run([
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--realm', domain,
            '-d', '5',
            'ads', 'testjoin'
        ], check=False, capture_output=True)

        if netads.returncode == 0:
            return True

        err_msg = netads.stderr.decode()
        log_path = f'{SMBPath.LOGDIR.platform()}/domain_testjoin_{time()}.log'
        with open(log_path, 'w') as f:
            os.fchmod(f.fileno(), 0o600)
            f.write(err_msg)
            f.flush()

        # We only want to forcible rejoin active directory if it's clear
        # that our credentials are wrong or the computer account doesn't
        # exist
        for err_str in (
            'Join to domain is not valid',
            '0xfffffff6',
            'LDAP_INVALID_CREDENTIALS',
            'The name provided is not a properly formed account name',
            'The attempted logon is invalid.'
        ):
            if err_str in err_msg:
                return False

        raise CallError(
            'Attempt to check AD join status failed unexpectedly. '
            f'Please review logs at {log_path} and file a bug report.'
        )

    def _ad_grant_privileges(self) -> None:
        """ Grant domain admins ability to manage TrueNAS """

        dom = wbclient.Ctx().domain()

        existing_privileges = self.middleware.call_sync(
            'privilege.query',
            [["name", "=", dom.dns_name.upper()]]
        )

        if existing_privileges:
            return

        try:
            self.middleware.call_sync('privilege.create', {
                'name': dom.dns_name.upper(),
                'ds_groups': [f'{dom.sid}-512'],
                'roles': ['FULL_ADMIN'],
                'web_shell': True
            })
        except Exception:
            # This should be non-fatal since admin can simply fix via
            # our webui
            self.logger.warning(
                'Failed to grant domain administrators access to the '
                'TrueNAS API.', exc_info=True
            )

    def _ad_post_join_actions(self, job: Job, conf: dict):
        self._ad_set_spn(conf['netbiosname'], conf['domainname'])
        # The password in secrets.tdb has been replaced so make
        # sure we have it backed up in our config.
        self.middleware.call_sync('directoryservices.secrets.backup')
        self.middleware.call_sync('activedirectory.register_dns')

        # start up AD service, but skip kerberos start for now
        self._ad_activate(False)

    def _ad_join_impl(self, job: Job, conf: dict):
        """
        Join an active directory domain. Requires admin kerberos ticket.
        If post-join operations fail, then we attempt to roll back changes on
        the DC.
        """
        cmd = [
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            '-d', '5',
            'ads', 'join',
        ]

        if conf['createcomputer']:
            cmd.append(f'createcomputer={conf["createcomputer"]}')

        cmd.extend([
            '--no-dns-updates', conf['domainname']
        ])

        netads = subprocess.run(cmd, check=False, capture_output=True)
        if netads.returncode != 0:
            err_msg = netads.stderr.decode().split(':', 1)[1]
            raise CallError(err_msg)

        # we've now successfully joined AD and can proceed with post-join
        # operations
        try:
            job.set_progress(60, 'Performing post-join actions')
            return self._ad_post_join_actions(job, conf)
        except KRB5Error:
            # if there's an actual unrecoverable kerberos error
            # in our post-join actions then leaving AD will also fail
            raise
        except Exception as e:
            # We failed to set up DNS / keytab cleanly
            # roll back and present user with error
            self._ad_leave(job, DSType.AD, conf['domainname'])
            self.middleware.call_sync('idmap.gencache.flush')
            raise e from None

    @kerberos_ticket
    def _ad_join(self, job: Job, ds_type: DSType, domain: str):
        ad_config = self.middleware.call_sync('activedirectory.config')
        smb = self.middleware.call_sync('smb.config')
        workgroup = smb['workgroup']

        if (failover_status := self.middleware.call_sync('failover.status')) not in ('MASTER', 'SINGLE'):
            raise CallError(
                f'{failover_status}: TrueNAS may only be joined to active directory '
                'through the active storage controller and if high availability is healthy.'
            )

        dc_info = self._ad_lookup_dc(ad_config['domainname'])

        job.set_progress(0, 'Preparing to join Active Directory')
        self.middleware.call_sync('etc.generate', 'smb')
        self.middleware.call_sync('etc.generate', 'hostname')

        """
        Kerberos realm field must be populated so that we can perform a kinit
        and use the kerberos ticket to execute 'net ads' commands.
        """
        job.set_progress(5, 'Configuring Kerberos Settings.')
        if not ad_config['kerberos_realm']:
            try:
                realm_id = self.middleware.call_sync(
                    'kerberos.realm.query',
                    [('realm', '=', ad_config['domainname'])],
                    {'get': True}
                )['id']
            except MatchNotFound:
                realm_id = self.middleware.call_sync(
                    'datastore.insert', 'directoryservice.kerberosrealm',
                    {'krb_realm': ad_config['domainname'].upper()}
                )

            self.middleware.call_sync(
                'datastore.update', 'directoryservice.activedirectory', ad_config['id'],
                {"kerberos_realm": realm_id}, {'prefix': 'ad_'}
            )
            ad_config['kerberos_realm'] = realm_id

        job.set_progress(20, 'Detecting Active Directory Site.')
        site = ad_config['site'] or dc_info['client_site_name']

        job.set_progress(30, 'Detecting Active Directory NetBIOS Domain Name.')
        if workgroup != dc_info['pre-win2k_domain']:
            self.middleware.call_sync('datastore.update', 'services.cifs', smb['id'], {
                'cifs_srv_workgroup': dc_info['pre-win2k_domain']
            })
            workgroup = dc_info['pre-win2k_domain']

        # Ensure smb4.conf has correct workgorup.
        self.middleware.call_sync('etc.generate', 'smb')

        job.set_progress(50, 'Performing domain join.')
        self._ad_join_impl(job, ad_config)
        machine_acct = f'{ad_config["netbiosname"].upper()}$@{ad_config["domainname"]}'
        self.middleware.call_sync('datastore.update', 'directoryservice.activedirectory', ad_config['id'], {
            'kerberos_principal': machine_acct,
            'site': site,
            'kerberos_realm': ad_config['kerberos_realm']
        }, {'prefix': 'ad_'})

        job.set_progress(75, 'Performing kinit using new computer account.')
        # Remove our temporary administrative ticket and replace with machine account.
        # Sysvol replication may not have completed (new account only exists on the DC we're
        # talking to) and so during this operation we need to hard-code which KDC we use for
        # the new kinit.
        domain_info = self._ad_domain_info(ad_config['domainname'])
        cred = self.middleware.call_sync('kerberos.get_cred', {
            'dstype': DSType.AD.value,
            'conf': {
                'domainname': ad_config['domainname'],
                'kerberos_principal': machine_acct,
            }
        })

        # remove admin ticket
        self.middleware.call_sync('kerberos.kdestroy')

        # remove stub krb5.conf to allow overriding with fix on KDC
        os.remove('/etc/krb5.conf')
        try:
            self.middleware.call_sync('kerberos.do_kinit', {
                'krb5_cred': cred,
                'kinit-options': {
                    'kdc_override': {'domain': ad_config['domainname'], 'kdc': domain_info['kdc_server']}
                }
            })
        except KRB5Error:
            # Attempt to kinit against DC we were talking to failed and so we'll switch to generic
            # kinit loop to wait for things to settle.
            self.logger.debug('Initial attempt to kinit with new kerberos pricipal failed. Starting kinit loop.', exc_info=True)
            job.set_progress(80, 'Waiting for active directory to replicate machine account changes.')
            self._ad_wait_kerberos_start()
        else:
            self.middleware.call_sync('kerberos.wait_for_renewal')
            self.middleware.call_sync('etc.generate', 'kerberos')

        self.middleware.call_sync('service.update', 'cifs', {'enable': True})

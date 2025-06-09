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
from middlewared.utils.directoryservices.common import ds_config_to_fqdn
from middlewared.utils.directoryservices.constants import DSCredType, DSType, DEF_SVC_OPTS
from middlewared.utils.directoryservices.credential import kinit_with_cred
from middlewared.utils.directoryservices.krb5 import (
    gss_dump_cred,
    gss_get_current_cred,
    kerberos_ticket,
    kdc_saf_cache_get,
)
from middlewared.utils.directoryservices.krb5_constants import (
    krb5ccache,
    KRB_Keytab,
    SAMBA_KEYTAB_DIR,
)
from middlewared.utils.directoryservices.krb5_error import (
    KRB5Error,
    KRB5ErrCode,
)
from middlewared.utils.netbios import validate_netbios_name, NETBIOSNAME_MAX_LEN
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
        return cred_info['name_type'] == DSCredType.KERBEROS_PRINCIPAL

    def _saf_kdc_name(self) -> str | None:
        if (kdc_override := kdc_saf_cache_get()) is None:
            return None

        if ptr := self.middleware.call_sync('dnsclient.reverse_lookup', {'addresses': [kdc_override]}):
            # strip trailing period because of unexpected interaction with libads
            return ptr[0]['target'].removesuffix('.')

        return None

    def _ad_activate(self, perform_kinit=True) -> None:
        for etc_file in DSType.AD.etc_files:
            self.middleware.call_sync('etc.generate', etc_file)

        self.middleware.call_sync('service.control', 'RESTART', 'idmap', DEF_SVC_OPTS).wait_sync(raise_error=True)

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

    def _ad_cleanup(self, job: Job, ds_config: dict):
        job.set_progress(description='Removing local configuration')
        self.middleware.call_sync('directoryservices.reset')

        # Remove the AD kerberos principal
        princ = self.middleware.call_sync('kerberos.keytab.query', [['name', '=', 'AD_MACHINE_ACCOUNT']])
        if princ:
            self.middleware.call_sync('datastore.delete', 'directoryservice.kerberoskeytab', princ[0]['id'])

        # Remove the AD kerberos realm
        if ds_config['kerberos_realm']:
            realm = self.middleware.call_sync('kerberos.realm.query', [['realm', '=', ds_config['kerberos_realm']]])
            if realm:
                self.middleware.call_sync('datastore.delete', 'directoryservice.kerberosrealm', realm[0]['id'])

        try:
            os.unlink(KRB_Keytab.SYSTEM.value)
        except Exception:
            pass

        for etc_file in DSType.AD.etc_files:
            self.middleware.call_sync('etc.generate', etc_file)

    def _ad_leave(self, job: Job, ds_config: dict):
        """ Delete our computer object from active directory """

        # remove all samba keytabs
        for file in os.listdir(SAMBA_KEYTAB_DIR):
            os.unlink(os.path.join(SAMBA_KEYTAB_DIR, file))

        job.set_progress(description='Removing machine account from Active Directory')
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

        # Above step nukes our secrets file so we can forcibly overwrite our secrets backup
        try:
            self.middleware.call_sync('directoryservices.secrets.backup')
        except Exception:
            self.logger.debug('Failed to remove stale secrets', exc_info=True)

        if ds_config['enable_dns_updates']:
            job.set_progress(description='Unregistering from active directory DNS')
            try:
                self.unregister_dns(ds_config_to_fqdn(ds_config), True)
            except Exception:
                # We're committed now and so we need to finish up our local reconfiguration
                self.logger.warning('Failed to unregister from active directory DNS. Manual cleanup required', exc_info=True)

        self._ad_cleanup(job, ds_config)
        job.set_progress(description='Completed active directory leave.')

    @kerberos_ticket
    def _ad_set_spn(self, hostname, domainname):
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

        setspn(f'nfs/{hostname.upper()}')
        setspn(f'nfs/{hostname.upper()}.{domainname.lower()}')
        self.middleware.call_sync('kerberos.keytab.store_ad_keytab')

    @kerberos_ticket
    def _ad_test_join(self, domain: str):
        """
        Test to see whether we're currently joined to an AD domain.
        """
        cmd = [SMBCmd.NET.value, '--use-kerberos', 'required', '--realm', domain, '-d', '5',]
        if kdc_override := self._saf_kdc_name():
            cmd.extend(['--server', kdc_override])

        netads = subprocess.run(cmd + ['ads', 'testjoin'], check=False, capture_output=True)
        if netads.returncode == 0:
            return True

        err_msg = netads.stderr.decode()
        log_path = f'{SMBPath.LOGDIR.path}/domain_testjoin_{time()}.log'
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

    def _ad_grant_privileges(self, domain: str) -> None:
        """ Grant domain admins ability to manage TrueNAS """

        dom = wbclient.Ctx().domain()

        existing_privileges = self.middleware.call_sync(
            'privilege.query',
            [["name", "=", domain.upper()]]
        )

        if existing_privileges:
            return

        try:
            self.middleware.call_sync('privilege.create', {
                'name': domain.upper(),
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
        domain = conf['configuration']['domain']
        hostname = conf['configuration']['hostname']

        self._ad_set_spn(hostname, domain)
        # The password in secrets.tdb has been replaced so make
        # sure we have it backed up in our config.
        self.middleware.call_sync('directoryservices.secrets.backup')

        if conf['enable_dns_updates']:
            # Register forward + reverse
            retries = 10
            while True:
                try:
                    self.register_dns(conf['dns_name'], True)
                    break
                except CallError as exc:
                    # Testing with domains with multiple DCs / nameservers indicated that
                    # slow sysvol replication can also cause GSSAPI errors in nsupdate
                    if not retries or 'Server not found in Kerberos database' not in exc.errmsg:
                        raise

                    self.logger.debug('%s: Failed to perform nsupdate due to potentially slow sysvol replication.',
                                      conf['dns_name'])
                    sleep(5)
                    retries -= 1

        # start up AD service, but skip kerberos start for now
        self._ad_activate(False)

    def _ad_join_impl(self, job: Job, conf: dict):
        """
        Join an active directory domain. Requires admin kerberos ticket.
        If post-join operations fail, then we attempt to roll back changes on
        the DC.
        """
        domain = conf['configuration']['domain']
        hostname = conf['configuration']['hostname']
        computer_account_ou = conf['configuration']['computer_account_ou']
        cmd = [
            SMBCmd.NET.value,
            '--use-kerberos', 'required',
            '--use-krb5-ccache', krb5ccache.SYSTEM.value,
            '-d', '5',
        ]
        if kdc_override := self._saf_kdc_name():
            cmd.extend(['--server', kdc_override])

        cmd.extend(['ads', 'join', f'dnshostname={hostname}.{domain}'])

        if computer_account_ou:
            cmd.append(f'createcomputer={computer_account_ou}')

        # we perform DNS updates as-needed in post_join_actions
        cmd.extend(['--no-dns-updates', domain])

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
            self.logger.debug('Post-join actions failed. Rolling back configuration', exc_info=True)
            self._ad_leave(job, conf)
            self.middleware.call_sync('idmap.gencache.flush')
            raise e from None

    @kerberos_ticket
    def _ad_join(self, job: Job, ds_config: dict):
        assert ds_config['service_type'] == 'ACTIVEDIRECTORY', 'Unexpected service configuration'
        domain = ds_config['configuration']['domain']
        hostname = ds_config['configuration']['hostname']
        realm_id = None

        if (failover_status := self.middleware.call_sync('failover.status')) not in ('MASTER', 'SINGLE'):
            raise CallError(
                f'{failover_status}: TrueNAS may only be joined to active directory '
                'through the active storage controller and if high availability is healthy.'
            )

        ngc = self.middleware.call_sync('network.configuration.config')
        smb = self.middleware.call_sync('smb.config')

        # Make some reasonable hostname guesses if user hasn't done override
        if not hostname:
            hostname = ngc.get('hostname_virtual') or ngc['hostname_local']

        # If user has specified a hostname to use for join, then overwrite other parts of config if needed
        elif hostname != (ngc.get('hostname_virtual') or ngc['hostname_local']):
            if ngc.get('hostname_virtual'):
                self.middleware.call_sync('network.configuration.update', {'hostname_virtual': hostname})
            else:
                self.middleware.call_sync('network.configuration.update', {'hostname': hostname})

        # Update the netbiosname to something reasonably related to our hostname
        # There are probably some legacy users who have "truenas" as the name of their server
        # because that was the default netbiosname. This isn't a great choice because if another device
        # joins AD with same generic name then it will clobber this one's computer account in AD, and so
        # we want to discourage that.
        if smb['netbiosname'] != hostname and smb['netbiosname'] == 'truenas':
            # Default netbiosname. We *really* don't want to collide with other servers.
            # We'll start by trying to truncate to max netbiosname length
            smb['netbiosname'] = hostname[:NETBIOSNAME_MAX_LEN - 1]

            # Allow job failure if our best guess at a valid netbiosname fails
            validate_netbios_name(smb['netbiosname'])
            self.middleware.call_sync('datastore.update', 'services.cifs', smb['id'], {'cifs_srv_netbiosname': smb['netbiosname']})

        ds_config['configuration']['hostname'] = hostname
        workgroup = smb['workgroup']

        dc_info = self._ad_lookup_dc(domain)

        job.set_progress(0, 'Preparing to join Active Directory')
        self.middleware.call_sync('etc.generate', 'smb')
        self.middleware.call_sync('etc.generate', 'hostname')

        """
        Kerberos realm field must be populated so that we can perform a kinit
        and use the kerberos ticket to execute 'net ads' commands.
        """
        job.set_progress(5, 'Configuring Kerberos Settings.')
        if not ds_config['kerberos_realm']:
            try:
                realm_id = self.middleware.call_sync(
                    'kerberos.realm.query',
                    [('realm', '=', domain)],
                    {'get': True}
                )['id']
            except MatchNotFound:
                realm_id = self.middleware.call_sync(
                    'datastore.insert', 'directoryservice.kerberosrealm',
                    {'krb_realm': domain.upper()}
                )

            ds_config['kerberos_realm'] = domain
        else:
            try:
                realm_id = self.middleware.call_sync('kerberos.realm.query', [
                    ['realm', '=', ds_config['kerberos_realm'].upper()]
                ], {'get': True})['id']
            except MatchNotFound:
                realm_id = self.middleware.call_sync(
                    'datastore.insert', 'directoryservice.kerberosrealm',
                    {'krb_realm': domain.upper()}
                )

        job.set_progress(20, 'Detecting Active Directory Site.')
        site = ds_config['configuration']['site'] or dc_info['client_site_name']

        job.set_progress(30, 'Detecting Active Directory NetBIOS Domain Name.')
        if workgroup != dc_info['pre-win2k_domain']:
            self.middleware.call_sync('datastore.update', 'services.cifs', smb['id'], {
                'cifs_srv_workgroup': dc_info['pre-win2k_domain']
            })
            workgroup = dc_info['pre-win2k_domain']

        # Update datastore with credential information. We do this before the
        # actual join so that correct kerberos information gets inserted into SMB config
        dns_name = ds_config_to_fqdn(ds_config) + '.'
        machine_acct = f'{smb["netbiosname"].upper()}$@{domain}'
        krb_cred = {'credential_type': DSCredType.KERBEROS_PRINCIPAL, 'principal': machine_acct}
        self.middleware.call_sync('datastore.update', 'directoryservices', ds_config['id'], {
            'cred_type': DSCredType.KERBEROS_PRINCIPAL,
            'cred_krb5': krb_cred,
            'ad_site': site,
            'kerberos_realm_id': realm_id
        })

        # Ensure smb4.conf has correct workgorup.
        self.middleware.call_sync('etc.generate', 'smb')

        job.set_progress(50, 'Performing domain join.')
        self._ad_join_impl(job, ds_config | {'dns_name': dns_name})

        # Get updated config
        ds_config = self.middleware.call_sync('directoryservices.config')

        job.set_progress(75, 'Performing kinit using new computer account.')
        # Remove our temporary administrative ticket and replace with machine account.
        # Sysvol replication may not have completed (new account only exists on the DC we're
        # talking to) and so during this operation we need to hard-code which KDC we use for
        # the new kinit.
        # remove admin ticket
        self.middleware.call_sync('kerberos.kdestroy')

        try:
            kinit_with_cred(krb_cred)
        except KRB5Error:
            # Attempt to kinit against DC we were talking to failed and so we'll switch to generic
            # kinit loop to wait for things to settle.
            self.logger.debug('Initial attempt to kinit with new kerberos pricipal failed. Starting kinit loop.', exc_info=True)
            job.set_progress(80, 'Waiting for active directory to replicate machine account changes.')
            self._ad_wait_kerberos_start()
        else:
            self.middleware.call_sync('etc.generate', 'kerberos')

        self.middleware.call_sync('kerberos.wait_for_renewal')

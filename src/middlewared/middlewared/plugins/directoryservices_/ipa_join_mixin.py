import base64
import json
import os
import subprocess

from dataclasses import asdict
from functools import cache
from middlewared.job import Job
from middlewared.plugins.ldap_.constants import SERVER_TYPE_FREEIPA
from middlewared.utils.directoryservices import (
    ipa, ipa_constants
)
from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.directoryservices.ipactl_constants import (
    ExitCode,
    IpaOperation,
)
from middlewared.utils.directoryservices.krb5 import kerberos_ticket, ktutil_list_impl
from middlewared.utils.directoryservices.krb5_error import KRB5ErrCode, KRB5Error
from middlewared.utils.lang import undefined
from middlewared.service_exception import CallError
from tempfile import NamedTemporaryFile

IPACTL = ipa_constants.IPACmd.IPACTL.value


def _parse_ipa_response(resp: subprocess.CompletedProcess) -> dict:
    """
    ipactl returns JSON-encoded data and depending on failure
    code may also include JSON-RPC response error message from
    IPA server.
    """
    match resp.returncode:
        case ExitCode.SUCCESS:
            return json.loads(resp.stdout.decode().strip())
        case ExitCode.JSON_ERROR:
            err = resp.stderr.decode().strip()
            err_decoded = json.loads(err)
            raise CallError(err, extra=err_decoded)
        case ExitCode.NO_SMB_SUPPORT:
            err = resp.stderr.decode().strip()
            raise FileNotFoundError(err)
        case _:
            err = resp.stderr or resp.stdout
            raise RuntimeError(f'{resp.returncode}: {err.decode()}')


class IPAJoinMixin:
    __ipa_smb_domain = undefined

    def _ipa_remove_kerberos_cert_config(self, job: Job | None, ldap_config: dict | None):
        if ldap_config is None:
            ldap_config = self.middleware.call_sync('ldap.config')

        if job:
            job.set_progress(80, 'Removing kerberos configuration.')

        if ldap_config['kerberos_realm']:
            # TODO: remove after unifying the directory services plugins
            # User may have configured our kerberos realm in AD plugin
            # necessitating deletion from config
            self.middleware.call_sync(
                'datastore.update', 'directoryservice.activedirectory', 1, {'ad_kerberos_realm': None}
            )
            self.middleware.call_sync('kerberos.realm.delete', ldap_config['kerberos_realm'])

        if (host_kt := self.middleware.call_sync('kerberos.keytab.query', [
            ['name', '=', ipa_constants.IpaConfigName.IPA_HOST_KEYTAB.value]
        ])):
            self.middleware.call_sync('kerberos.keytab.delete', host_kt[0]['id'])

        if job:
            job.set_progress(90, 'Removing IPA certificate.')
        if (ipa_cert := self.middleware.call_sync('certificate.query', [
            ['name', '=', ipa_constants.IpaConfigName.IPA_CACERT.value]
        ])):
            delete_job = self.middleware.call_sync('certificate.delete', ipa_cert[0]['id'])
            delete_job.wait_sync(raise_error=True)

    def _ipa_leave(self, job: Job, ds_type: DSType, domain: str):
        """
        Leave the IPA domain
        """
        ldap_config = self.middleware.call_sync('ldap.config')
        ipa_config = self.middleware.call_sync('ldap.ipa_config', ldap_config)

        if ipa_config['domain'] != domain:
            raise CallError(f'{domain}: TrueNAS is joined to {ipa_config["domain"]}')

        job.set_progress(0, 'Deleting NFS and SMB service principals.')
        self._ipa_del_spn()

        job.set_progress(10, 'Removing DNS entries.')
        self.unregister_dns(ipa_config['host'], False)

        # now leave IPA
        job.set_progress(30, 'Leaving IPA domain.')
        try:
            join = subprocess.run([
                IPACTL, '-a', IpaOperation.LEAVE.name
            ], check=False, capture_output=True)
            _parse_ipa_response(join)
        except Exception:
            self.logger.warning(
                'Failed to disable TrueNAS machine account in the IPA domain. '
                'Further action by the IPA administrator to fully remove '
                'the server from the domain will be required.', exc_info=True
            )

        # At this point we can start removing local configuration
        job.set_progress(50, 'Disabling LDAP service.')

        # This disables the LDAP service and cancels any in progress cache
        # jobs
        ldap_update_job = self.middleware.call_sync('ldap.update', {
            'binddn': '',
            'bindpw': '',
            'kerberos_principal': '',
            'kerberos_realm': None,
            'enable': False,
        })

        ldap_update_job.wait_sync()

        self._ipa_remove_kerberos_cert_config(job, ldap_config)

        job.set_progress(95, 'Removing privileges.')
        if (priv := self.middleware.call_sync('privilege.query', [
            ['name', '=', ipa_config['domain'].upper()]
        ])):
            self.middleware.call_sync('privilege.delete', priv[0]['id'])

        job.set_progress(100, 'IPA leave complete.')

    def _ipa_activate(self) -> None:
        for etc_file in DSType.IPA.etc_files:
            self.middleware.call_sync('etc.generate', etc_file)

        self.middleware.call_sync('service.control', 'STOP', 'sssd').wait_sync(raise_error=True)
        self.middleware.call_sync('service.control', 'START', 'sssd', {'silent': False}).wait_sync(raise_error=True)
        self.middleware.call_sync('kerberos.start')

    def _ipa_insert_keytab(self, service: ipa_constants.IpaConfigName, keytab_data: str) -> None:
        """ Insert a keytab into the TrueNAS config (replacing existing) """
        if service is ipa_constants.IpaConfigName.IPA_CACERT:
            raise ValueError('Not a keytab file')

        kt_name = service.value
        if kt_entry := self.middleware.call_sync('kerberos.keytab.query', [
            ['name', '=', kt_name]
        ]):
            self.middleware.call_sync(
                'datastore.update', 'directoryservice.kerberoskeytab',
                kt_entry[0]['id'],
                {'keytab_name': kt_name, 'keytab_file': keytab_data}
            )
        else:
            self.middleware.call_sync(
                'datastore.insert', 'directoryservice.kerberoskeytab',
                {'keytab_name': kt_name, 'keytab_file': keytab_data}
            )

    def _ipa_grant_privileges(self) -> None:
        """ Grant domain admins ability to manage TrueNAS """

        ipa_config = self.middleware.call_sync('ldap.ipa_config')

        existing_privileges = self.middleware.call_sync(
            'privilege.query',
            [["name", "=", ipa_config['domain'].upper()]]
        )

        if existing_privileges:
            return

        try:
            admins_grp = self.middleware.call_sync('group.get_group_obj', {
                'groupname': 'admins',
                'sid_info': True
            })
        except Exception:
            self.logger.debug(
                'Failed to look up admins group for IPA domain. API access for admin '
                'accounts will have to be manually configured', exc_info=True
            )
            return

        match admins_grp['source']:
            case 'LDAP':
                pass
            case 'LOCAL':
                self.logger.warning(
                    'Local "admins" group collides with name of group provided '
                    'by IPA domain, which prevents the IPA group from being '
                    'automatically granted API access.'
                )
                return
            case _:
                self.logger.warning(
                    '%s: unexpected source for "admins" group, which prevents '
                    'the IPA group from being automatically granted API access.',
                    admins_grp['source']
                )
                return

        try:
            self.middleware.call_sync('privilege.create', {
                'name': ipa_config['domain'].upper(),
                'ds_groups': [admins_grp['gr_gid']],
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

    @kerberos_ticket
    def _ipa_test_join(self, dstype, domain):
        """
        Rudimentary check for whether we've already joined IPA domain

        This allows us to force a re-join if user has deleted relevant
        config information.
        """
        ldap_conf = self.middleware.call_sync('ldap.config')
        if ldap_conf['server_type'] != SERVER_TYPE_FREEIPA:
            return False

        if not ldap_conf['kerberos_realm']:
            return False

        if not self.middleware.call_sync('ldap.has_ipa_host_keytab'):
            return False

        ipa_config = self.middleware.call_sync('ldap.ipa_config', ldap_conf)
        return ipa_config['domain'].casefold() == domain.casefold()

    @kerberos_ticket
    def _ipa_set_spn(self):
        """ internal method to create service entries on remote IPA server """
        output = []
        for op, spn_type in (
            (IpaOperation.SET_SMB_PRINCIPAL, ipa_constants.IpaConfigName.IPA_SMB_KEYTAB),
            (IpaOperation.SET_NFS_PRINCIPAL, ipa_constants.IpaConfigName.IPA_NFS_KEYTAB)
        ):
            setspn = subprocess.run([IPACTL, '-a', op.name], check=False, capture_output=True)

            try:
                resp = _parse_ipa_response(setspn)
                output.append(resp | {'keytab_type': spn_type})
            except FileNotFoundError:
                self.logger.debug('IPA domain does not provide support for SMB protocol')
                continue
            except Exception:
                self.logger.error('%s: failed to create keytab', op.name, exc_info=True)

        return output

    @kerberos_ticket
    def _ipa_del_spn(self):
        """ internal method to delete service principals on remote IPA server

        Perform remote operation and then delete keytab from datastore. At this point
        the host keytab is not deleted because we need it to remove our DNS entries.
        """
        for op, spn_type in (
            (IpaOperation.DEL_SMB_PRINCIPAL, ipa_constants.IpaConfigName.IPA_SMB_KEYTAB),
            (IpaOperation.DEL_NFS_PRINCIPAL, ipa_constants.IpaConfigName.IPA_NFS_KEYTAB)
        ):
            setspn = subprocess.run([IPACTL, '-a', op.name], check=False, capture_output=True)
            try:
                _parse_ipa_response(setspn)
            except Exception:
                self.logger.warning('%s: failed to remove service principal from remote IPA server.',
                                    op.name, exc_info=True)

            if (kt := self.middleware.call_sync('kerberos.keytab.query', [['name', '=', spn_type]])):
                self.middleware.call_sync('kerberos.keytab.delete', kt[0]['id'])

    @kerberos_ticket
    def _ipa_setup_services(self, job: Job):
        job.set_progress(60, 'Configuring kerberos principals')
        resp = self._ipa_set_spn()
        domain_info = None

        for entry in resp:
            self._ipa_insert_keytab(entry['keytab_type'], entry['keytab'])
            if entry['keytab_type'] is ipa_constants.IpaConfigName.IPA_SMB_KEYTAB:
                domain_info = entry['domain_info'][0]
                password = entry['password']

        if domain_info:
            job.set_progress(70, 'Configuring SMB server for IPA')
            self.middleware.call_sync('datastore.update', 'services.cifs', 1, {
                'cifs_srv_workgroup': domain_info['netbios_name']
            })

            # regenerate our SMB config to apply our new domain
            self.middleware.call_sync('etc.generate', 'smb')

            # write our domain sid to the secrets.tdb
            setsid = subprocess.run([
                'net', 'setdomainsid', domain_info['domain_sid']
            ], capture_output=True, check=False)

            if setsid.returncode:
                raise CallError(f'Failed to set domain SID: {setsid.stderr.decode()}')

            # We must write the password encoded in the SMB keytab
            # to secrets.tdb at this point.
            self.middleware.call_sync(
                'directoryservices.secrets.set_ipa_secret',
                domain_info['netbios_name'],
                base64.b64encode(password.encode())
            )

            self.middleware.call_sync('directoryservices.secrets.backup')

    @kerberos_ticket
    def ipa_get_smb_domain_info(self) -> dict | None:
        """
        This information shouldn't change during normal course of
        operations in a FreeIPA domain. Cache a copy of it for future
        reference.

        There are three possible states for this.

        1. we've never checked before. In this case __ipa_smb_domain will be an
           `undefined` object

        2. we've checked but the IPA LDAP schema contains no SMB-related information
           for some reason. In this case __ipa_smb_domain will be set to None

        3. we've checked and have SMB domain info in which case we've stored an
           IPASmbDomain instance and return it in dictionary form
        """
        if self.__ipa_smb_domain is None:
            return None

        elif self.__ipa_smb_domain is not undefined:
            return asdict(self.__ipa_smb_domain)

        if self.middleware.call_sync('directoryservices.status')['type'] != DSType.IPA.value:
            raise CallError('Not joined to IPA domain')

        getdom = subprocess.run([
            IPACTL, '-a', IpaOperation.SMB_DOMAIN_INFO.name,
        ], check=False, capture_output=True)

        resp = _parse_ipa_response(getdom)
        if not resp:
            self.__ipa_smb_domain = None
            return None

        self.__ipa_smb_domain = ipa_constants.IPASmbDomain(
            netbios_name=resp[0]['netbios_name'],
            domain_sid=resp[0]['domain_sid'],
            domain_name=resp[0]['domain_name'],
            range_id_min=resp[0]['range_id_min'],
            range_id_max=resp[0]['range_id_max']
        )
        return asdict(self.__ipa_smb_domain)

    @cache
    def _ipa_get_cacert(self) -> str:
        """ retrieve PEM-encoded CACERT from IPA LDAP server """
        getca = subprocess.run([
            IPACTL, '-a', IpaOperation.GET_CACERT_FROM_LDAP.name,
        ], check=False, capture_output=True)

        resp = _parse_ipa_response(getca)
        return resp['cacert']

    def _ipa_join_impl(self, host: str, basedn: str, domain: str, realm: str, server: str) -> dict:
        """
        Write the IPA default config file (preliminary step to getting our cacert).

        Then obtain the ipa cacert and write it in /etc/ipa (where tools expect to find it).
        This allows us to call ipa-join successfully using the kerberos ticket
        we already have (checked when _ipa_join() is called).

        Add the cacert to the JSON-RPC response to the ipa-join request so that
        caller can insert into our DB. If this fails we should remove the config
        files we wrote so that we don't end up in semi-configured state.
        """

        # First write our freeipa config (this allows us to get our cert)
        try:
            ipa.write_ipa_default_config(host, basedn, domain, realm, server)

            ipa_cacert = self._ipa_get_cacert()
            ipa.write_ipa_cacert(ipa_cacert.encode())

            # Now we should be able to join
            join = subprocess.run([
                IPACTL, '-a', IpaOperation.JOIN.name
            ], check=False, capture_output=True)
            resp = _parse_ipa_response(join)
            resp['cacert'] = ipa_cacert
        except Exception as e:
            for p in (
                ipa_constants.IPAPath.DEFAULTCONF.path,
                ipa_constants.IPAPath.CACERT.path
            ):
                try:
                    os.remove(p)
                except FileNotFoundError:
                    pass
            raise e

        return resp

    @kerberos_ticket
    def _ipa_join(self, job: Job, ds_type: DSType, domain: str):
        """
        This method performs all the steps required to join TrueNAS to an
        IPA domain and update our TrueNAS configuration with details gleaned
        from the IPA domain settings. Once it is completed we will:


        1. have created host account in IPA domain
        2. registered our IP addresses in IPA
        3. stored up to three keytabs on TrueNAS (host, nfs, and smb)
        4. stored the IPA cacert on TrueNAS
        5. updated samba's secrets.tdb to contain the info from SMB keytab
        6. backed up samba's secrets.tdb
        """
        ldap_config = self.middleware.call_sync('ldap.config')
        ipa_config = self.middleware.call_sync('ldap.ipa_config', ldap_config)
        self.__ipa_smb_domain = undefined

        job.set_progress(15, 'Performing IPA join')
        resp = self._ipa_join_impl(
            ipa_config['host'],
            ipa_config['basedn'],
            ipa_config['domain'],
            ipa_config['realm'],
            ipa_config['target_server']
        )
        # resp includes `cacert` for domain and `keytab` for our host principal to use
        # in future.

        # insert the IPA host principal keytab into our database
        job.set_progress(50, 'Updating TrueNAS configuration with IPA domain details.')
        self._ipa_insert_keytab(ipa_constants.IpaConfigName.IPA_HOST_KEYTAB, resp['keytab'])

        # make sure database also has the IPA realm
        ipa_realm = self.middleware.call_sync('kerberos.realm.query', [
            ['realm', '=', ipa_config['realm']]
        ])
        if ipa_realm:
            ipa_realm_id = ipa_realm[0]['id']
        else:
            ipa_realm_id = self.middleware.call_sync(
                'datastore.insert', 'directoryservice.kerberosrealm',
                {'krb_realm': ipa_config['realm']}
            )

        with NamedTemporaryFile() as f:
            f.write(base64.b64decode(resp['keytab']))
            f.flush()
            krb_principal = ktutil_list_impl(f.name)[0]['principal']

        # update our cacerts with IPA domain one:
        existing_cacert = self.middleware.call_sync('certificate.query', [
            ['name', '=', ipa_constants.IpaConfigName.IPA_CACERT.value]
        ])
        if existing_cacert:
            if existing_cacert[0]['certificate'] != resp['cacert']:
                # We'll continue to try joining the IPA domain and hope for the best.
                # It's technically possible that we will still be able to validate
                # the cert / have working SSL.
                self.logger.error(
                    '[%s]: Stored CA certificate for IPA domain does not match '
                    'certificate returned from the IPA LDAP server. This may '
                    'prevent the IPA directory service from properly functioning '
                    'and should be resolved by the TrueNAS administrator. '
                    'An example of such adminstrative action would be to remove '
                    'the possibly incorrect CA certificate from the TrueNAS '
                    'server and re-join the IPA domain to ensure the correct '
                    'CA certificate is installed after reviewing the issue with '
                    'the person or team responsible for maintaining the IPA domain.',
                    ipa_constants.IpaConfigName.IPA_CACERT.value
                )
        else:
            cert_job = self.middleware.call_sync('certificate.create', {
                'name': ipa_constants.IpaConfigName.IPA_CACERT.value,
                'certificate': resp['cacert'],
                'add_to_trusted_store': True,
                'create_type': 'CERTIFICATE_CREATE_IMPORTED',
            })
            cert_job.wait_sync(raise_error=True)

        # make sure ldap service is updated to use realm and principal and
        # clear out the bind account password since it is no longer needed. We
        # don't insert the IPA cacert into the LDAP configuration since the
        # certificate field is for certificate-based authentication and _not_
        # providing certificate authority certificates
        self.middleware.call_sync('datastore.update', 'directoryservice.ldap', ldap_config['id'], {
            'ldap_kerberos_realm': ipa_realm_id,
            'ldap_kerberos_principal': krb_principal,
            'ldap_bindpw': ''
        })

        # We've joined API and have a proper host principal. Time to destroy admin keytab.
        self.middleware.call_sync('kerberos.kdestroy')

        # GSS-TSIG in IPA domain requires using our HOST kerberos principal
        try:
            self.middleware.call_sync('kerberos.start')
        except KRB5Error as err:
            match err.krb5_code:
                case KRB5ErrCode.KRB5_REALM_UNKNOWN:
                    # DNS is broken in the IPA domain and so we need to roll back our config
                    # changes.

                    saved_config = self.middleware.call_sync('ldap.config')

                    self.logger.warning(
                        'Unable to resolve kerberos realm via DNS. This may indicate misconfigured '
                        'nameservers on the TrueNAS server or a misconfigured IPA domain.', exc_info=True
                    )
                    self.middleware.call('datastore.update', 'directoryservice.ldap', ldap_config['id'], {
                        'ldap_kerberos_realm': None,
                        'ldap_kerberos_principal': '',
                        'ldap_bindpw': ldap_config['bindpw']
                    })

                    self._ipa_remove_kerberos_cert_config(None, saved_config)

                    # remove any configuration files we have written
                    for p in (
                        ipa_constants.IPAPath.DEFAULTCONF.path,
                        ipa_constants.IPAPath.CACERT.path
                    ):
                        try:
                            os.remove(p)
                        except FileNotFoundError:
                            pass
                case _:
                    # Log the complete error message so that we have opportunity to improve error
                    # handling for weird kerberos errors.
                    self.logger.error('Failed to obtain kerberos ticket with host keytab.', exc_info=True)

            raise err

        # Verify that starting kerberos got the correct cred
        cred = self.middleware.call_sync('kerberos.check_ticket')
        if cred['name_type'] != 'KERBEROS_PRINCIPAL':
            # This shouldn't happen, but we must fail here since the nsupdate will
            # fail with REJECTED.
            raise CallError(f'{cred}: unexpected kerberos credential type')
        elif not cred['name'].startswith('host/'):
            raise CallError(f'{cred}: not host principal.')

        self.register_dns(ipa_config['host'])
        self._ipa_setup_services(job)
        job.set_progress(75, 'Activating IPA service.')
        self._ipa_activate()

        # Wrap around cache fill because this forces a wait until IPA becomes ready
        cache_fill = self.middleware.call_sync('directoryservices.cache.refresh_impl')
        cache_fill.wait_sync()

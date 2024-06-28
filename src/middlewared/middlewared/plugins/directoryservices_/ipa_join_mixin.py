import base64
import json
import ldap
import os
import subprocess

from functools import cache
from middlewared.job import Job
from middlewared.utils.directoryservices import (
    ipa, ipa_constants
)
from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.directoryservices.ipactl_constants import (
    ExitCode,
    IpaOperation,
)
from middlewared.utils.directoryservices.krb5 import kerberos_ticket, ktutil_list_impl
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

    def _ipa_insert_keytab(self, service: ipa_constants.IpaConfigName, keytab_data: str) -> None:
        if service is ipa_constants.IpaConfigName.IPA_CACERT:
            raise ValueError('Not a keytab file')

        kt_name = service.value
        if kt_entry := self.call_sync('kerberos.keytab.query', [
            ['name', '=', kt_name]
        ]):
            self.call_sync(
                'datastore.update', 'directoryservice.kerberoskeytab',
                kt_entry[0]['id'],
                {'keytab_name': kt_name, 'keytab_file': keytab_data}
            )
        else:
            self.call_sync(
                'datastore.insert', 'directoryservice.kerberoskeytab',
                {'keytab_name': kt_name, 'keytab_file': keytab_data}
            )

    @kerberos_ticket
    def _ipa_set_spn(self):
        """ internal method to create service entries on remote IPA server """
        output = []
        for op, spn_type in (
            (IpaOperation.SET_SMB_PRINCIPAL, ipa_constants.IpaConfigName.IPA_SMB_KEYTAB),
            (IpaOperation.SET_NFS_PRINCIPAL, ipa_constants.IpaConfigName.IPA_NFS_KEYTAB)
        ):
            try:
                setspn = subprocess.run([
                    IPACTL,
                    '-a', IpaOperation.SET_SMB_PRINCIPAL.name
                ], check=False, capture_output=True)
            except FileNotFoundError:
                continue

            resp = self._parse_ipa_response(setspn)
            output.append(resp | {'keytab_type': spn_type})

        return output

    @kerberos_ticket
    def _ipa_setup_services(self):
        resp = self._ipa_set_spn()
        domain_info = None

        for entry in resp:
            self._ipa_insert_keytab(entry['keytab_type'], entry['keytab'])
            if entry['keytab_type'] is ipa_constants.IpaConfigName.IPA_SMB_KEYTAB:
                domain_info = entry['domain_info']

        if domain_info:
            self.middleware.call_sync('datastore.update', 'services.cifs', 1, {
                'workgroup': domain_info['netbios_name']
            })

            # We must write the password encoded in the SMB keytab
            # to secrets.tdb at this point.
            self.middleware.call_sync(
                'directoryservices.secrets.set_ipa_secret',
                base64.b64encode(domain_info['password'].encode())
            )

    @kerberos_ticket
    @cache
    def _ipa_get_smb_domain_info(self):
        """
        This information shouldn't change during normal course of
        operations in a FreeIPA domain. Cache a copy of it for future
        reference.
        """
        getdom = subprocess.run([
            IPACTL, '-a', IpaOperation.SMB_DOMAIN_INFO.name,
        ], check=False, capture_output=True)

        resp = self._parse_ipa_response(getdom)
        return resp[0] if resp else {}

    @cache
    def _ipa_get_cacert(self) -> str:
        """ retrieve PEM-encoded CACERT from IPA LDAP server """
        getca = subprocess.run([
            IPACTL, '-a', IpaOperation.GET_CACERT_FROM_LDAP.name,
        ], check=False, capture_output=True)

        resp = self._parse_ipa_response(getca)
        return resp['cacert']

    def _ipa_join_impl(self, host: str, domain: str, realm: str, server: str) -> dict:

        # First write our freeipa config (this allows us to get our cert)
        try:
            ipa.write_ipa_default_config(host, domain, realm, server)

            ipa_cacert = self._ipa_get_cacert(True)
            ipa.write_ipa_cacert(ipa_cacert.encode())

            # Now we should be able to join
            join = subprocess.run([
                IPACTL, '-a', IpaOperation.JOIN.name
            ], check=False, capture_output=True)
            resp = self._parse_ipa_response(join)
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
        ipa_config = self.middleware.call_sync('ldap.ipa_config')
        ldap_config = self.middleware.call_sync('ldap.config')

        job.set_progress(5, 'Preparing to kinit to IPA domain')
        username = f'{ipa_config["username"]}@{ipa_config["realm"]}'
        self.middleware.call_sync('kerberos.do_kinit', {
            'krb5_cred': {
                'username': username,
                'password': ldap_config['bindpw']
            },
            'kinit-options': {
                'kdc_override': {
                    'domain': ipa_config['realm'],
                    'kdc': ipa_config['target_server']
                }
            }
        })

        # We have ticket, which means that our configuration
        # is mostly correct. We _should_ be able to actually
        # join FreeIPA now.
        job.set_progress(15, 'Performing IPA join')
        resp = self._join_impl(
            ipa_config['host'],
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
        existing_cacert = self.middleware.call_sync('certificateauthority.query', [
            ['name', '=', ipa_constants.IpaConfigName.IPA_CACERT.value]
        ])
        if existing_cacert:
            if existing_cacert[0]['certificate'] != resp['cacert']:
                self.logger.error(
                    '[%s]: Stored CA certificate for IPA domain does not match '
                    'certificate returned from the IPA LDAP server. Removing '
                    'certificate from the IPA server configuration. This may '
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
            self.middleware.call_sync('certificateauthority.create', {
                'name': ipa_constants.IpaConfigName.IPA_CACERT.value,
                'certificate': resp['cacert'],
                'add_to_trusted_store': True,
                'create_type': 'CA_CREATE_IMPORTED'
            })

        # make sure ldap service is updated to use realm and principal and
        # clear out the bind account password since it is no longer needed. We
        # don't insert the IPA cacert into the LDAP configuration since the
        # certificate field is for certificate-based authentication and _not_
        # providing certificate authority certificates
        self.middleware.call_sync('datastore.update', 'directoryservice.ldap', ldap['id'], {
            'ldap_kerberos_realm': ipa_realm_id,
            'ldap_kerberos_principal': krb_principal,
            'ldap_bindpw': ''
        })

        self._ipa_setup_services(job)

import enum
import errno
import ipaddress
import ldap as pyldap
import os
import socket
import struct

from urllib.parse import urlparse
from middlewared.schema import accepts, returns, Bool, Dict, Int, List, Str, Ref, LDAP_DN
from middlewared.service import job, private, ConfigService, Service, ValidationErrors
from middlewared.service_exception import CallError
import middlewared.sqlalchemy as sa
from middlewared.plugins.directoryservices import DSStatus, SSL
from middlewared.plugins.idmap import DSType
from middlewared.plugins.ldap_.ldap_client import LdapClient
from middlewared.plugins.ldap_ import constants
from middlewared.utils.nss import pwd, grp
from middlewared.utils.nss.nss_common import NssModule
from middlewared.validators import Range


LDAP_DEPRECATED = "LDAP with SMB schema support"


class SAMAccountType(enum.Enum):
    SAM_DOMAIN_OBJECT = 0x0
    SAM_GROUP_OBJECT = 0x10000000
    SAM_NON_SECURITY_GROUP_OBJECT = 0x10000001
    SAM_ALIAS_OBJECT = 0x20000000
    SAM_NON_SECURITY_ALIAS_OBJECT = 0x20000001
    SAM_USER_OBJECT = 0x30000000
    SAM_NORMAL_USER_ACCOUNT = 0x30000000
    SAM_MACHINE_ACCOUNT = 0x30000001
    SAM_TRUST_ACCOUNT = 0x30000002
    SAM_APP_BASIC_GROUP = 0x40000000
    SAM_APP_QUERY_GROUP = 0x40000001


class LDAPClient(Service):
    class Config:
        private = True

    @accepts(Dict(
        'ldap-configuration',
        List('uri_list', required=True),
        Str('bind_type', enum=['ANONYMOUS', 'PLAIN', 'GSSAPI', 'EXTERNAL'], required=True),
        LDAP_DN('basedn', required=True),
        Dict(
            'credentials',
            LDAP_DN('binddn', default=''),
            Str('bindpw', default='', private=True),
        ),
        Dict(
            'security',
            Str('ssl', enum=["OFF", "ON", "START_TLS"]),
            Str('sasl', enum=['SIGN', 'SEAL'], default='SEAL'),
            Str('client_certificate', null=True, default=''),
            Bool('validate_certificates', default=True),
        ),
        Dict(
            'options',
            Int('timeout', default=30, validators=[Range(min_=1, max_=45)]),
            Int('dns_timeout', default=5, validators=[Range(min_=1, max_=45)]),
        ),
        register=True,
    ))
    def validate_credentials(self, data):
        """
        Verify that credentials are working by closing any existing LDAP bind
        and performing a fresh bind.
        """
        try:
            LdapClient.open(data, True)
        except Exception as e:
            self._convert_exception(e)

    def _name_to_errno(self, ldaperr):
        err = errno.EFAULT
        if ldaperr == "INVALID_CREDENTIALS":
            err = errno.EPERM
        elif ldaperr == "NO_SUCH_OBJECT":
            err = errno.ENOENT
        elif ldaperr == "INVALID_DN_SYNTAX":
            err = errno.EINVAL

        return err

    def _local_error_to_errno(self, info):
        err = errno.EFAULT
        err_summary = None
        if 'Server not found in Kerberos database' in info:
            err = errno.ENOENT
            err_summary = "KRB5KDC_ERR_C_PRINCIPAL_UNKNOWN"

        return (err, err_summary)

    def _convert_exception(self, ex):
        if issubclass(type(ex), pyldap.LDAPError) and ex.args:
            desc = ex.args[0].get('desc')
            info = ex.args[0].get('info')
            err_str = f"{desc}: {info}" if info else desc
            err = self._name_to_errno(type(ex).__name__)
            raise CallError(err_str, err, type(ex).__name__)
        if issubclass(ex, pyldap.LOCAL_ERROR):
            info = ex.args[0].get('info')
            err, err_summary = self._local_error_to_errno(info)
            raise CallError(info, err, err_summary)
        else:
            raise CallError(str(ex))

    def parse_results(self, results):
        res = []
        for r in results:
            parsed_data = {}
            if len(r) > 1 and isinstance(r[1], dict):
                for k, v in r[1].items():
                    try:
                        v = list(i.decode() for i in v)
                    except Exception:
                        v = list(str(i) for i in v)
                    parsed_data.update({k: v})

                res.append({
                    'dn': r[0],
                    'data': parsed_data
                })
            else:
                self.logger.debug("Unable to parse results: %s", r)

        return res

    @accepts(Dict(
        'get-samba-domain',
        Ref('ldap-configuration'),
    ))
    def get_samba_domains(self, data):
        """
        This returns a list of configured samba domains on the LDAP
        server. This is used to determine whether the LDAP server has
        The Samba LDAP schema. In this case, the SMB service can be
        configured to use Samba's ldapsam passdb backend.
        """
        try:
            results = LdapClient.search(
                data['ldap-configuration'],
                data['ldap-configuration']['basedn'],
                pyldap.SCOPE_SUBTREE,
                '(objectclass=sambaDomain)'
            )
        except Exception as e:
            self._convert_exception(e)

        return self.parse_results(results)

    @accepts(Dict(
        'get-root-dse',
        Ref('ldap-configuration'),
    ))
    def get_root_dse(self, data):
        """
        root DSE query is defined in RFC4512 as a search operation
        with an empty baseObject, scope of baseObject, and a filter of
        "(objectClass=*)"
        In theory this should be accessible with an anonymous bind. In practice,
        it's better to use proper auth because configurations can vary wildly.
        """
        results = LdapClient.search(
            data['ldap-configuration'], '', pyldap.SCOPE_BASE, '(objectclass=*)'
        )
        return self.parse_results(results)

    @accepts(Dict(
        'get-dn',
        LDAP_DN('dn', default='', null=True),
        Str('scope', default='SUBTREE', enum=['BASE', 'SUBTREE']),
        Ref('ldap-configuration'),
    ))
    def get_dn(self, data):
        results = LdapClient.search(
            data['ldap-configuration'],
            data['dn'] or data['ldap-configuration']['basedn'],
            pyldap.SCOPE_SUBTREE if data['scope'] == 'SUBTREE' else pyldap.SCOPE_BASE,
            '(objectclass=*)'
        )

        return self.parse_results(results)

    @accepts()
    def close_handle(self):
        LdapClient.close()


class LDAPModel(sa.Model):
    __tablename__ = 'directoryservice_ldap'

    id = sa.Column(sa.Integer(), primary_key=True)
    ldap_hostname = sa.Column(sa.String(120))
    ldap_basedn = sa.Column(sa.String(120))
    ldap_binddn = sa.Column(sa.String(256))
    ldap_bindpw = sa.Column(sa.EncryptedText())
    ldap_anonbind = sa.Column(sa.Boolean())
    ldap_ssl = sa.Column(sa.String(120))
    ldap_timeout = sa.Column(sa.Integer())
    ldap_dns_timeout = sa.Column(sa.Integer())
    ldap_has_samba_schema = sa.Column(sa.Boolean())
    ldap_auxiliary_parameters = sa.Column(sa.Text())
    ldap_schema = sa.Column(sa.String(120))
    ldap_enable = sa.Column(sa.Boolean())
    ldap_certificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    ldap_kerberos_realm_id = sa.Column(sa.ForeignKey('directoryservice_kerberosrealm.id'), index=True, nullable=True)
    ldap_kerberos_principal = sa.Column(sa.String(255))
    ldap_validate_certificates = sa.Column(sa.Boolean(), default=True)
    ldap_disable_freenas_cache = sa.Column(sa.Boolean())
    ldap_base_user = sa.Column(sa.String(256), nullable=True)
    ldap_base_group = sa.Column(sa.String(256), nullable=True)
    ldap_base_netgroup = sa.Column(sa.String(256), nullable=True)
    ldap_user_object_class = sa.Column(sa.String(256), nullable=True)
    ldap_user_name = sa.Column(sa.String(256), nullable=True)
    ldap_user_uid = sa.Column(sa.String(256), nullable=True)
    ldap_user_gid = sa.Column(sa.String(256), nullable=True)
    ldap_user_gecos = sa.Column(sa.String(256), nullable=True)
    ldap_user_home_directory = sa.Column(sa.String(256), nullable=True)
    ldap_user_shell = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_object_class = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_last_change = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_min = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_max = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_warning = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_inactive = sa.Column(sa.String(256), nullable=True)
    ldap_shadow_expire = sa.Column(sa.String(256), nullable=True)
    ldap_group_object_class = sa.Column(sa.String(256), nullable=True)
    ldap_group_gid = sa.Column(sa.String(256), nullable=True)
    ldap_group_member = sa.Column(sa.String(256), nullable=True)
    ldap_netgroup_object_class = sa.Column(sa.String(256), nullable=True)
    ldap_netgroup_member = sa.Column(sa.String(256), nullable=True)
    ldap_netgroup_triple = sa.Column(sa.String(256), nullable=True)
    ldap_server_type = sa.Column(sa.String(256), nullable=True)


class LDAPService(ConfigService):

    class Config:
        service = "ldap"
        datastore = 'directoryservice.ldap'
        datastore_extend = "ldap.ldap_extend"
        datastore_prefix = "ldap_"
        cli_namespace = "directory_service.ldap"
        role_prefix = "DIRECTORY_SERVICE"

    ENTRY = Dict(
        'ldap_update',
        List('hostname', default=None),
        LDAP_DN('basedn'),
        LDAP_DN('binddn'),
        Str('bindpw', private=True),
        Bool('anonbind', default=False),
        Ref('ldap_ssl_choice', 'ssl'),
        Int('certificate', null=True),
        Bool('validate_certificates', default=True),
        Bool('disable_freenas_cache'),
        Int('timeout', default=30),
        Int('dns_timeout', default=5),
        Int('kerberos_realm', null=True),
        Str('kerberos_principal'),
        Str('auxiliary_parameters', max_length=None),
        Ref('nss_info_ldap', 'schema'),
        Bool('enable'),
        constants.LDAP_SEARCH_BASES_SCHEMA,
        constants.LDAP_ATTRIBUTE_MAP_SCHEMA,
        register=True,
    )

    @private
    async def ldap_conf_to_client_config(self, data=None):
        if data is None:
            data = await self.config()

        if not data['enable']:
            raise CallError("LDAP directory service is not enabled.")

        client_config = {
            "uri_list": data["uri_list"],
            "basedn": data.get("basedn", ""),
            "credentials": {
                "binddn": "",
                "bindpw": "",
            },
            "security": {
                "ssl": data["ssl"],
                "sasl": "SEAL",
                "client_certificate": data["cert_name"],
                "validate_certificates": data["validate_certificates"],
            },
            "options": {
                "timeout": data["timeout"],
                "dns_timeout": data["dns_timeout"],
            }
        }
        if data['anonbind']:
            client_config['bind_type'] = 'ANONYMOUS'
        elif data['cert_name']:
            client_config['bind_type'] = 'EXTERNAL'
        elif data['kerberos_realm']:
            client_config['bind_type'] = 'GSSAPI'
        else:
            client_config['bind_type'] = 'PLAIN'
            client_config['credentials'] = {
                'binddn': data['binddn'],
                'bindpw': data['bindpw']
            }

        return client_config

    @private
    async def ldap_extend(self, data):
        data['hostname'] = data['hostname'].split(',') if data['hostname'] else []
        for key in ["ssl", "schema"]:
            data[key] = data[key].upper()

        if data["certificate"] is not None:
            data["cert_name"] = data['certificate']['cert_name']
            data["certificate"] = data['certificate']['id']
        else:
            data["cert_name"] = None

        if data["kerberos_realm"] is not None:
            data["kerberos_realm"] = data["kerberos_realm"]["id"]

        data['uri_list'] = await self.hostnames_to_uris(data)

        # The following portion of ldap_extend shifts ldap search base and map
        # parameter overrides into their own separate dictionaries
        # "search_bases" and "attribute_maps" respectively
        data[constants.LDAP_SEARCH_BASES_SCHEMA_NAME] = {}
        data[constants.LDAP_ATTRIBUTE_MAP_SCHEMA_NAME] = {
            nss_type: {} for nss_type in constants.LDAP_ATTRIBUTE_MAPS.keys()
        }

        for key in constants.LDAP_SEARCH_BASE_KEYS:
            data[constants.LDAP_SEARCH_BASES_SCHEMA_NAME][key] = data.pop(key, None)

        for nss_type, keys in constants.LDAP_ATTRIBUTE_MAPS.items():
            for key in keys:
                data[constants.LDAP_ATTRIBUTE_MAP_SCHEMA_NAME][nss_type][key] = data.pop(key, None)

        return data

    @private
    async def ldap_compress(self, data):
        data['hostname'] = ','.join(data['hostname'])
        for key in ["ssl", "schema"]:
            data[key] = data[key].lower()

        data.pop('uri_list')
        data.pop('cert_name')
        search_bases = data.pop(constants.LDAP_SEARCH_BASES_SCHEMA_NAME, {})
        attribute_maps = data.pop(constants.LDAP_ATTRIBUTE_MAP_SCHEMA_NAME, {})

        # Flatten the search_bases and attribute_maps prior to DB insertion
        for key in constants.LDAP_SEARCH_BASE_KEYS:
            data[key] = search_bases.get(key)

        for nss_type, keys in constants.LDAP_ATTRIBUTE_MAPS.items():
            for key in keys:
                data[key] = attribute_maps[nss_type].get(key)

        return data

    @accepts(roles=['DIRECTORY_SERVICE_READ'])
    @returns(List('schema_choices', items=[Ref('nss_info_ldap')]))
    async def schema_choices(self):
        """
        Returns list of available LDAP schema choices.
        """
        return await self.middleware.call('directoryservices.nss_info_choices', 'LDAP')

    @accepts(roles=['DIRECTORY_SERVICE_READ'])
    @returns(List('ssl_choices', items=[Ref('ldap_ssl_choice', 'ssl')]))
    async def ssl_choices(self):
        """
        Returns list of SSL choices.
        """
        return await self.middleware.call('directoryservices.ssl_choices', 'LDAP')

    @private
    async def hostnames_to_uris(self, data):
        ret = []
        for h in data['hostname']:
            proto = 'ldaps' if SSL(data['ssl']) == SSL.USESSL else 'ldap'
            parsed = urlparse(f"{proto}://{h}")
            try:
                port = parsed.port
                host = parsed.netloc if not parsed.port else parsed.netloc.rsplit(':', 1)[0]
            except ValueError:
                """
                ParseResult.port will raise a ValueError if the port is not an int
                Ignore for now. ValidationError will be raised in common_validate()
                """
                host, port = h.rsplit(':', 1)

            if port is None:
                port = 636 if SSL(data['ssl']) == SSL.USESSL else 389

            uri = f"{proto}://{host}:{port}"
            ret.append(uri)

        return ret

    @private
    async def common_validate(self, new, old, verrors):
        if not new["enable"]:
            return

        ad_enabled = (await self.middleware.call("activedirectory.config"))['enable']
        if ad_enabled:
            verrors.add(
                "ldap_update.enable",
                "LDAP service may not be enabled while Active Directory service is enabled."
            )

        if new["certificate"]:
            verrors.extend(await self.middleware.call(
                "certificate.cert_services_validation",
                new["certificate"], "ldap_update.certificate", False
            ))

        if not new["bindpw"] and not new["kerberos_principal"] and not new["anonbind"]:
            verrors.add(
                "ldap_update.binddn",
                "Bind credentials or kerberos keytab are required for an authenticated bind."
            )
        if new["bindpw"] and new["kerberos_principal"]:
            new["bindpw"] = ""

        if not new["basedn"]:
            verrors.add(
                "ldap_update.basedn",
                "The basedn parameter is required."
            )
        if not new["hostname"]:
            verrors.add(
                "ldap_update.hostname",
                "The LDAP hostname parameter is required."
            )
        for idx, uri in enumerate(new["uri_list"]):
            parsed = urlparse(uri)
            try:
                port = parsed.port

            except ValueError:
                verrors.add(f"ldap_update.hostname.{idx}",
                            f"Invalid port number: [{port}].")

    @private
    async def convert_ldap_err_to_verr(self, data, e, verrors):
        if e.extra == "INVALID_CREDENTIALS":
            verrors.add('ldap_update.binddn',
                        'Remote LDAP server returned response that '
                        'credentials are invalid.')

        elif e.extra == "STRONG_AUTH_NOT_SUPPORTED" and data['certificate']:
            verrors.add('ldap_update.certificate',
                        'Certificate-based authentication is not '
                        f'supported by remote LDAP server: {e.errmsg}.')

        elif e.extra == "NO_SUCH_OBJECT":
            verrors.add('ldap_update.basedn',
                        'Remote LDAP server returned "NO_SUCH_OBJECT". This may '
                        'indicate that the base DN is syntactically correct, but does '
                        'not exist on the server.')

        elif e.extra == "INVALID_DN_SYNTAX":
            verrors.add('ldap_update.basedn',
                        'Remote LDAP server returned that the base DN is '
                        'syntactically invalid.')

        elif e.extra == "KRB5KDC_ERR_C_PRINCIPAL_UNKNOWN":
            verrors.add('ldap_update.kerberos_principal',
                        'SASL GSSAPI failed with error (Client not found in kerberos '
                        'database). This may indicate a misconfiguration in DNS server '
                        'triggering a failure to validate the kerberos principal via '
                        'reverse lookup zone. Exact error returned by kerberos library is '
                        f'as follows: {e.errmsg}')

        elif e.extra:
            verrors.add('ldap_update', f'[{e.extra}]: {e.errmsg}')

        else:
            verrors.add('ldap_update', e.errmsg)

    @private
    async def object_sid_to_string(self, objectsid):
        version = struct.unpack('B', objectsid[0:1])[0]
        if version != 1:
            raise CallError(f"{version}: Invalid SID version")

        sid_length = struct.unpack('B', objectsid[1:2])[0]
        authority = struct.unpack(b'>Q', b'\x00\x00' + objectsid[2:8])[0]
        objectsid = objectsid[8:]

        if len(objectsid) != 4 * sid_length:
            raise CallError("Invalid SID length")

        output_sid = f'S-{version}-{authority}'
        for v in struct.iter_unpack('<L', objectsid):
            output_sid += f'-{v[0]}'

        return output_sid

    @private
    async def ldap_validate(self, old, data, verrors):
        for idx, h in enumerate(data['uri_list']):
            host, port = urlparse(h).netloc.rsplit(':', 1)
            try:
                await self.middleware.call('ldap.port_is_listening', host, int(port), data['dns_timeout'])
            except Exception as e:
                verrors.add(
                    f'ldap_update.hostname.{idx}',
                    f'Failed to open socket to remote LDAP server: {e}'
                )
                return

        try:
            await self.validate_credentials(data)
        except CallError as e:
            await self.convert_ldap_err_to_verr(data, e, verrors)
            return

        if not set(old['hostname']) & set(data['hostname']):
            # No overlap between old and new hostnames and so force server_type autodetection
            data['server_type'] = None

        if not data['server_type'] and data['enable']:
            data['server_type'] = await self.autodetect_ldap_settings(data)
            if data['server_type'] == constants.SERVER_TYPE_ACTIVE_DIRECTORY:
                verrors.add(
                    'ldap_update.hostname',
                    'Active Directoy plugin must be used to join Active Directory domains.'
                )

    @private
    async def autodetect_ldap_settings(self, data):
        """
        The root dse on remote LDAP server contains basic LDAP configuration information.
        By the time this method is called we have already been able to complete an LDAP
        bind with the provided credentials.

        This method provides basic LDAP server implementation specific configuration
        parameters that can later be fine-tuned by the admin if they are undesired.
        """
        rootdse = (await self.middleware.call('ldap.get_root_DSE', data))[0]['data']

        if 'vendorName' in rootdse:
            """
            FreeIPA domain. For now assume in this case that vendorName will
            be 389 project.
            """
            if rootdse['vendorName'][0] != '389 Project':
                self.logger.debug(
                    '%s: unrecognized vendor name, setting LDAP server type to GENERIC',
                    rootdse['vendorName'][0]
                )
                return constants.SERVER_TYPE_GENERIC

            default_naming_context = rootdse['defaultnamingcontext'][0]
            data.update({'schema': 'RFC2307BIS'})
            bases = data[constants.LDAP_SEARCH_BASES_SCHEMA_NAME]
            bases[constants.SEARCH_BASE_USER] = f'cn=users,cn=accounts,{default_naming_context}'
            bases[constants.SEARCH_BASE_GROUP] = f'cn=groups,cn=accounts,{default_naming_context}'
            bases[constants.SEARCH_BASE_NETGROUP] = f'cn=ng,cn=compat,{default_naming_context}'
            return constants.SERVER_TYPE_FREEIPA

        elif 'domainControllerFunctionality' in rootdse:
            """
            ActiveDirectory domain.
            """
            return constants.SERVER_TYPE_ACTIVE_DIRECTORY

        elif 'objectClass' in rootdse:
            """
            OpenLDAP
            """
            if 'OpenLDAProotDSE' not in rootdse['objectClass']:
                self.logger.debug(
                    '%s: unexpected objectClass values in LDAP root DSE',
                    rootdse['objectClass']
                )
                return constants.SERVER_TYPE_GENERIC

            return constants.SERVER_TYPE_OPENLDAP

        return constants.SERVER_TYPE_GENERIC

    @accepts(Ref('ldap_update'))
    @job(lock="ldap_start_stop")
    async def do_update(self, job, data):
        """
        `hostname` list of ip addresses or hostnames of LDAP servers with
        which to communicate in order of preference. Failover only occurs
        if the current LDAP server is unresponsive.

        `basedn` specifies the default base DN to use when performing ldap
        operations. The base must be specified as a Distinguished Name in LDAP
        format.

        `binddn` specifies the default bind DN to use when performing ldap
        operations. The bind DN must be specified as a Distinguished Name in
        LDAP format.

        `anonbind` use anonymous authentication.

        `ssl` establish SSL/TLS-protected connections to the LDAP server(s).
        GSSAPI signing is disabled on SSL/TLS-protected connections if
        kerberos authentication is used.

        `certificate` LDAPs client certificate to be used for certificate-
        based authentication.

        `validate_certificates` specifies whether to perform checks on server
        certificates in a TLS session. If enabled, TLS_REQCERT demand is set.
        The server certificate is requested. If no certificate is provided or
        if a bad certificate is provided, the session is immediately terminated.
        If disabled, TLS_REQCERT allow is set. The server certificate is
        requested, but all errors are ignored.

        `kerberos_realm` in which the server is located. This parameter is
        only required for SASL GSSAPI authentication to the remote LDAP server.

        `kerberos_principal` kerberos principal to use for SASL GSSAPI
        authentication to the remote server. If `kerberos_realm` is specified
        without a keytab, then the `binddn` and `bindpw` are used to
        perform to obtain the ticket necessary for GSSAPI authentication.

        `timeout` specifies  a  timeout  (in  seconds) after which calls to
        synchronous LDAP APIs will abort if no response is received.

        `dns_timeout` specifies the timeout (in seconds) after which the
        poll(2)/select(2) following a connect(2) returns in case of no activity
        for openldap. For nslcd this specifies the time limit (in seconds) to
        use when connecting to the directory server. This directly impacts the
        length of time that the LDAP service tries before failing over to
        a secondary LDAP URI.

        The following are advanced settings are configuration parameters for
        handling LDAP servers that do not fully comply with RFC-2307. In most
        situations all of the following parameters should be set to null,
        which indicates to backend to use default for the specified NSS info
        schema.

        `search_bases` - these parameters allow specifying a non-standard
        search base for users (`base_user`), groups (`base_group`), and
        netgroups (`base_netgroup`). Must be a valid LDAP DN. No remote
        validation is performed that the search base exists or contains
        expected objects.

        `attribute_maps` - allow specifying alternate non-RFC-compliant
        attribute names for `passwd`, `shadow`, `group`, and `netgroup` object
        classes as specified in RFC 2307. Setting key to `null` has special
        meaning that RFC defaults for the configure `nss_info_schema` will
        be used.

        `server_type` is a readonly key indicating the server_type detected
        internally by TrueNAS. Value will be set to one of the following:
        `ACTIVE_DIRECTORY`, `FREEIPA`, `GENERIC`, and `OPENLDAP`. Generic
        is default if TrueNAS is unable to determine LDAP server type via
        information in the LDAP root DSE.
        """
        verrors = ValidationErrors()
        must_reload = False
        old = await self.config()
        new = old.copy()
        new_search_bases = data.pop(constants.LDAP_SEARCH_BASES_SCHEMA_NAME, {})
        new_attributes = data.pop(constants.LDAP_ATTRIBUTE_MAP_SCHEMA_NAME, {})
        if data['hostname'] is None:
            del(data['hostname'])

        new.update(data)
        new[constants.LDAP_SEARCH_BASES_SCHEMA_NAME] | new_search_bases

        for nss_type in constants.LDAP_ATTRIBUTE_MAPS.keys():
            new[constants.LDAP_ATTRIBUTE_MAP_SCHEMA_NAME][nss_type] | new_attributes.get(nss_type, {})

        new['uri_list'] = await self.hostnames_to_uris(new)
        await self.common_validate(new, old, verrors)
        verrors.check()

        if data.get('certificate') and data['certificate'] != old['certificate']:
            new_cert = await self.middleware.call('certificate.query',
                                                  [('id', '=', data['certificate'])],
                                                  {'get': True})
            new['cert_name'] = new_cert['name']

        if old != new:
            must_reload = True
            if new['enable']:
                await self.ldap_validate(old, new, verrors)
                verrors.check()

        await self.ldap_compress(new)
        await self.middleware.call('datastore.update', self._config.datastore, new['id'], new, {'prefix': 'ldap_'})

        if must_reload:
            if new['enable']:
                await self.__start(job)
            else:
                await self.__stop(job)

        return await self.config()

    @private
    def port_is_listening(self, host, port, timeout=1):
        ret = False

        try:
            ipaddress.IPv6Address(host)
            s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        except ipaddress.AddressValueError:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if timeout:
            s.settimeout(timeout)

        try:
            s.connect((host, port))
            ret = True

        except Exception as e:
            raise CallError(e)

        finally:
            s.close()

        return ret

    @private
    async def kinit(ldap_conf):
        if await self.middleware.call(
            'kerberos.check_ticket',
            {'ccache': krb5ccache.SYSTEM.name},
            False
        ):
            return

        payload = {
            'dstype': DSType.DS_TYPE_LDAP.name,
            'conf': {
                'binddn': ldap_config.get('binddn', ''),
                'bindpw': ldap_config.get('bindpw', ''),
                'kerberos_realm': ldap_config.get('kerberos_realm', ''),
                'kerberos_principal': ldap_config.get('kerberos_principal', ''),
            }
        }
        cred = await self.middleware.call('kerberos.get_cred', payload)
        await self.middleware.call('kerberos.do_kinit', {'krb5_cred': cred})

    @private
    async def validate_credentials(self, ldap_config=None):
        client_conf = await self.ldap_conf_to_client_config(ldap_config)
        if client_conf['bind_type'] == 'GSSAPI':
            await self.kinit(ldap_config)

        await self.middleware.call('ldapclient.validate_credentials', client_conf)

    @private
    async def get_samba_domains(self, ldap_config=None):
        client_conf = await self.ldap_conf_to_client_config(ldap_config)
        return await self.middleware.call('ldapclient.get_samba_domains', {"ldap-configuration": client_conf})

    @private
    async def get_root_DSE(self, ldap_config=None):
        """
        root DSE is defined in RFC4512, and must include the following:

        `namingContexts` naming contexts held in the LDAP sever

        `subschemaSubentry` subschema entries known by the LDAP server

        `altServer` alternative servers in case this one is unavailable

        `supportedExtension` list of supported extended operations

        `supportedControl` list of supported controls

        `supportedSASLMechnaisms` recognized Simple Authentication and Security layers
        (SASL) [RFC4422] mechanisms.

        `supportedLDAPVersion` LDAP versions implemented by the LDAP server

        In practice, this full data is not returned from many LDAP servers
        """
        client_conf = await self.ldap_conf_to_client_config(ldap_config)
        return await self.middleware.call('ldapclient.get_root_dse', {"ldap-configuration": client_conf})

    @private
    async def get_dn(self, dn=None, scope=None, ldap_config=None):
        """
        Outputs contents of specified DN in JSON. By default will target the basedn.
        """
        client_conf = await self.ldap_conf_to_client_config(ldap_config)
        payload = {
            "dn": dn,
            "ldap-configuration": client_conf,
        }
        if scope:
            payload['scope'] = scope

        return await self.middleware.call('ldapclient.get_dn', payload)

    @private
    async def started(self):
        """
        Returns False if disabled, True if healthy, raises exception if faulted.
        """
        verrors = ValidationErrors()
        ldap = await self.config()
        if not ldap['enable']:
            return False

        await self.common_validate(ldap, ldap, verrors)
        try:
            verrors.check()
        except ValidationErrors:
            await self.middleware.call(
                'datastore.update', self._config.datastore, 1,
                {'enable': False}, {'prefix': 'ldap_'}
            )
            raise CallError('Automatically disabling LDAP service due to invalid configuration.',
                            errno.EINVAL)

        """
        Initialize state to "JOINING" until after booted.
        """
        if not await self.middleware.call('system.ready'):
            await self.set_state(DSStatus['JOINING'])
            return True

        try:
            await self.get_root_DSE(ldap)
        except CallError:
            raise
        except Exception as e:
            raise CallError(e)

        if not await self.middleware.call('service.started', 'sssd'):
            await self.middleware.call('etc.generate', 'ldap')
            await self.middleware.call('service.start', 'sssd')

        await self.set_state(DSStatus['HEALTHY'])
        return True

    @private
    async def get_workgroup(self, ldap=None):
        ret = None
        smb = await self.middleware.call('smb.config')
        if ldap is None:
            ldap = await self.config()

        ret = await self.middleware.call('ldap.get_samba_domains', ldap)
        if len(ret) > 1:
            self.logger.warning('Multiple Samba Domains detected in LDAP environment '
                                'auto-configuration of workgroup map have failed: %s', ret)

        ret = ret[0]['data']['sambaDomainName'][0] if ret else []

        if ret and smb['workgroup'] != ret:
            self.logger.debug(f'Updating SMB workgroup to match the LDAP domain name [{ret}]')
            await self.middleware.call('smb.update', {'workgroup': ret})

        return ret

    @private
    async def set_state(self, state):
        return await self.middleware.call('directoryservices.set_state', {'ldap': state.name})

    @accepts(roles=['DIRECTORY_SERVICE_READ'])
    @returns(Ref('directoryservice_state'))
    async def get_state(self):
        """
        Wrapper function for 'directoryservices.get_state'. Returns only the state of the
        LDAP service.
        """
        return (await self.middleware.call('directoryservices.get_state'))['ldap']

    @private
    def create_sssd_dirs(self):
        os.makedirs('/var/run/sssd-cache/mc', mode=0o755, exist_ok=True)
        os.makedirs('/var/run/sssd-cache/db', mode=0o755, exist_ok=True)

    @private
    async def __start(self, job):
        """
        Refuse to start service if the service is alreading in process of starting or stopping.
        If state is 'HEALTHY' or 'FAULTED', then stop the service first before restarting it to ensure
        that the service begins in a clean state.
        """
        ldap_state = await self.middleware.call('ldap.get_state')
        if ldap_state in ['LEAVING', 'JOINING']:
            raise CallError(f'LDAP state is [{ldap_state}]. Please wait until directory service operation completes.', errno.EBUSY)

        job.set_progress(0, 'Preparing to configure LDAP directory service.')
        ldap = await self.config()

        await self.middleware.call('ldap.create_sssd_dirs')

        if ldap['kerberos_realm']:
            job.set_progress(5, 'Starting kerberos')
            await self.middleware.call('kerberos.start')

        job.set_progress(15, 'Generating configuration files')
        await self.middleware.call('etc.generate', 'rc')
        await self.middleware.call('etc.generate', 'ldap')
        await self.middleware.call('etc.generate', 'pam')

        job.set_progress(30, 'Starting sssd service')
        await self.middleware.call('service.restart', 'sssd')

        await self.set_state(DSStatus['HEALTHY'])

        job.set_progress(80, 'Restarting dependent services')
        cache_job = await self.middleware.call('directoryservices.cache.refresh')
        await cache_job.wait()
        await self.middleware.call('directoryservices.restart_dependent_services')

        job.set_progress(100, 'LDAP directory service started.')

    @private
    async def __stop(self, job):
        ldap_state = await self.middleware.call('ldap.get_state')
        if ldap_state in ['LEAVING', 'JOINING']:
            raise CallError(f'LDAP state is [{ldap_state}]. Please wait until directory service operation completes.', errno.EBUSY)

        job.set_progress(0, 'Preparing to stop LDAP directory service.')
        await self.middleware.call('alert.oneshot_delete', 'DeprecatedServiceConfiguration', LDAP_DEPRECATED)
        await self.set_state(DSStatus['LEAVING'])
        job.set_progress(10, 'Rewriting configuration files.')
        await self.middleware.call('etc.generate', 'rc')
        await self.middleware.call('etc.generate', 'ldap')
        await self.middleware.call('etc.generate', 'pam')

        job.set_progress(50, 'Clearing directory service cache.')
        await self.middleware.call('service.stop', 'dscache')

        job.set_progress(80, 'Stopping sssd service.')
        await self.middleware.call('service.stop', 'sssd')
        await self.set_state(DSStatus['DISABLED'])
        job.set_progress(100, 'LDAP directory service stopped.')

    @private
    @job(lock='fill_ldap_cache')
    def fill_cache(self, job, force=False):
        user_next_index = group_next_index = 100000000
        if (self.middleware.call_sync('ldap.config'))['disable_freenas_cache']:
            self.logger.debug('LDAP cache is disabled. Bypassing cache fill.')
            return

        pwd_list = pwd.getpwall(module=NssModule.SSS.name, as_dict=True)[NssModule.SSS.name]
        grp_list = grp.getgrall(module=NssModule.SSS.name, as_dict=True)[NssModule.SSS.name]

        for u in pwd_list:
            entry = {
                'id': user_next_index,
                'uid': u['pw_uid'],
                'username': u['pw_name'],
                'unixhash': None,
                'smbhash': None,
                'group': {},
                'home': u['pw_dir'],
                'shell': '',
                'full_name': u['pw_gecos'],
                'builtin': False,
                'email': '',
                'password_disabled': False,
                'locked': False,
                'sudo_commands': [],
                'sudo_commands_nopasswd': [],
                'attributes': {},
                'groups': [],
                'sshpubkey': None,
                'local': False,
                'id_type_both': False,
                'nt_name': None,
                'smb': True,
                'sid': None,
            }
            self.middleware.call_sync('directoryservices.cache.insert', self._config.namespace.upper(), 'USER', entry)
            user_next_index += 1

        for g in grp_list:
            entry = {
                'id': group_next_index,
                'gid': g['gr_gid'],
                'name': g['gr_name'],
                'group': g['gr_name'],
                'builtin': False,
                'sudo_commands': [],
                'sudo_commands_nopasswd': [],
                'users': [],
                'local': False,
                'id_type_both': False,
                'nt_name': None,
                'smb': True,
                'sid': None,
            }
            self.middleware.call_sync('directoryservices.cache.insert', self._config.namespace.upper(), 'GROUP', entry)
            group_next_index += 1

    @private
    async def get_cache(self):
        users = await self.middleware.call('directoryservices.cache.entries', self._config.namespace.upper(), 'USER')
        groups = await self.middleware.call('directoryservices.cache.entries', self._config.namespace.upper(), 'GROUP')
        return {"USERS": users, "GROUPS": groups}

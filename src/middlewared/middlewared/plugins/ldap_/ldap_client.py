import copy
import threading
import ldap as pyldap

from ldap.controls import SimplePagedResultsControl
from middlewared.utils.directoryservices.constants import SSL

client_lock = threading.RLock()


def ldap_client_lock(fn):
    def inner(*args, **kwargs):
        with client_lock:
            return fn(*args, **kwargs)

    return inner


class LDAPClient:

    pagesize = 1024
    _handle = None
    ldap_parameters = None

    def __init__(self):
        pyldap.protocol_version = pyldap.VERSION3
        pyldap.set_option(pyldap.OPT_REFERRALS, 0)

    def __setup_ssl(self, data):
        if SSL(data['security']['ssl']) == SSL.NOSSL:
            return

        cert = data['security']['client_certificate']
        if cert:
            pyldap.set_option(
                pyldap.OPT_X_TLS_CERTFILE,
                f"/etc/certificates/{cert}.crt"
            )
            pyldap.set_option(
                pyldap.OPT_X_TLS_KEYFILE,
                f"/etc/certificates/{cert}.key"
            )

        pyldap.set_option(
            pyldap.OPT_X_TLS_CACERTFILE,
            '/etc/ssl/certs/ca-certificates.crt'
        )

        if data['security']['validate_certificates']:
            pyldap.set_option(
                pyldap.OPT_X_TLS_REQUIRE_CERT,
                pyldap.OPT_X_TLS_DEMAND
            )
        else:
            pyldap.set_option(
                pyldap.OPT_X_TLS_REQUIRE_CERT,
                pyldap.OPT_X_TLS_ALLOW
            )

        pyldap.set_option(pyldap.OPT_X_TLS_NEWCTX, 0)

    def __perform_bind(self, data, uri, raise_error=True):
        try:
            self._handle = pyldap.initialize(uri)
        except Exception:
            self._handle = None
            if not raise_error:
                return False

            raise

        pyldap.set_option(pyldap.OPT_NETWORK_TIMEOUT, data['options']['dns_timeout'])

        self.__setup_ssl(data)
        if SSL(data['security']['ssl']) == SSL.USESTARTTLS:
            try:
                self._handle.start_tls_s()

            except Exception:
                self._handle = None
                if not raise_error:
                    return False
                raise

        try:
            if data['bind_type'] == 'ANONYMOUS':
                bound = self._handle.simple_bind_s()
            elif data['bind_type'] == 'EXTERNAL':
                bound = self._handle.sasl_non_interactive_bind_s('EXTERNAL')
            elif data['bind_type'] == 'GSSAPI':
                self._handle.set_option(pyldap.OPT_X_SASL_NOCANON, 1)
                self._handle.sasl_gssapi_bind_s()
                bound = True
            else:
                bound = self._handle.simple_bind_s(
                    data['credentials']['binddn'],
                    data['credentials']['bindpw']
                )
        except Exception:
            self._handle = None
            if not raise_error:
                return False
            raise

        return bound

    @ldap_client_lock
    def open(self, data, force_new=False):
        """
        We can only intialize a single host. In this case,
        we iterate through a list of hosts until we get one that
        works and then use that to set our LDAP handle.

        SASL GSSAPI bind only succeeds when DNS reverse lookup zone
        is correctly populated. Fall through to simple bind if this
        fails.
        """
        bound = False
        if self._handle and self.ldap_parameters == data and not force_new:
            return

        elif self._handle:
            self.close()
            self._handle = None

        if not data['uri_list']:
            raise ValueError("No URIs specified")

        saved_error = None

        for server in data['uri_list']:
            try:
                bound = self.__perform_bind(data, server)
            except Exception as e:
                saved_error = e
                bound = False
                continue

            if bound:
                break

        if not bound:
            self.handle = None
            if saved_error:
                raise saved_error
            else:
                raise RuntimeError(f"Failed to bind to URIs: {data['uri_list']}")

        self.ldap_parameters = copy.deepcopy(data)
        return

    @ldap_client_lock
    def close(self):
        if self._handle:
            self._handle.unbind()
            self._handle = None
            self.ldap_parameters = None

    @ldap_client_lock
    def search(self, ldap_config, basedn='', scope=pyldap.SCOPE_SUBTREE, filterstr='', sizelimit=0):
        self.open(ldap_config)
        result = []
        clientctrls = None
        paged = SimplePagedResultsControl(
            criticality=False,
            size=self.pagesize,
            cookie=''
        )
        paged_ctrls = {SimplePagedResultsControl.controlType: SimplePagedResultsControl}
        retry = True

        page = 0
        while True:
            serverctrls = [paged]

            try:
                id_ = self._handle.search_ext(
                    basedn,
                    scope,
                    filterstr=filterstr,
                    attrlist=None,
                    attrsonly=0,
                    serverctrls=serverctrls,
                    clientctrls=clientctrls,
                    timeout=ldap_config['options']['timeout'],
                    sizelimit=sizelimit
                )

                (rtype, rdata, rmsgid, serverctrls) = self._handle.result3(
                    id_, resp_ctrl_classes=paged_ctrls
                )
            except Exception:
                # our session may have died, try to re-open one time before failing.
                if not retry:
                    raise

                self.open(ldap_config, True)
                retry = False
                continue

            result.extend(rdata)

            paged.size = 0
            paged.cookie = cookie = None
            for sc in serverctrls:
                if sc.controlType == SimplePagedResultsControl.controlType:
                    cookie = sc.cookie
                    if cookie:
                        paged.cookie = cookie
                        paged.size = self.pagesize

                        break

            if not cookie:
                break

            page += 1

        return result


LdapClient = LDAPClient()

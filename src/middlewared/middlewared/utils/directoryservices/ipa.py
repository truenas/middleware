from configparser import RawConfigParser
from io import StringIO

from truenas_os_pyutils.io import atomic_write

from .ipa_constants import IPAPath


def generate_ipa_default_config(
    host: str,
    basedn: str,
    domain: str,
    realm: str,
    server: str
) -> bytes:
    """
    Return bytes of freeipa configuration file.

    IPA-related tools / ipa command relies on configuration file
    generated via python's RawConfigParser.

    For meaning of options see man (5) default.conf

    sample config:

    ```
    [global]
    basedn = dc=walkerdom,dc=test
    realm = WALKERDOM.TEST
    domain = walkerdom.test
    server = ipa.walkerdom.test
    host = truenas.walkerdom.test
    xmlrpc_uri = https://ipa.walkerdom.test/ipa/xml
    enable_ra = True
    ```
    """
    config = RawConfigParser()
    config.add_section('global')
    config.set('global', 'host', host)
    config.set('global', 'basedn', basedn)
    config.set('global', 'realm', realm)
    config.set('global', 'domain', domain)
    config.set('global', 'server', server)
    config.set('global', 'xmlrpc_uri', f'https://{server}/ipa/xml')
    config.set('global', 'enable_ra', 'False')

    with StringIO() as buf:
        config.write(buf)
        buf.seek(0)

        return buf.read().encode()


def _write_ipa_file(ipa_path: IPAPath, data: bytes) -> str:
    with atomic_write(ipa_path.path, 'wb', tmppath=IPAPath.IPADIR.path, perms=ipa_path.perm) as f:
        f.write(data)
    return ipa_path.path


def write_ipa_default_config(
    host: str,
    basedn: str,
    domain: str,
    realm: str,
    server: str
) -> str:
    """ Write the freeipa default.conf file based on the specified arguments """
    config = generate_ipa_default_config(host, basedn, domain, realm, server)
    return _write_ipa_file(IPAPath.DEFAULTCONF, config)


def write_ipa_cacert(cacert_bytes: bytes) -> str:
    return _write_ipa_file(IPAPath.CACERT, cacert_bytes)


def ldap_dn_to_realm(ldap_dn: str) -> str:
    """ Extract a hypothetical kerberos realm from DC components of LDAP DN. """
    realm_parts = []
    for component in ldap_dn.split(','):
        if not (parts := component.split('dc=')):
            continue

        realm_parts.append(parts[1].strip())

    return '.'.join(realm_parts)

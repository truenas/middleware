import os

from .ipa_constants import IPAPath
from configparser import RawConfigParser
from io import StringIO
from tempfile import NamedTemporaryFile


def generate_ipa_default_config(
    host: str,
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
    config.set('global', 'realm', realm)
    config.set('global', 'domain', domain)
    config.set('global', 'server', server)
    config.set('global', 'xmlrpc_uri', f'https://{server}/ipa/xml')
    config.set('global', 'enable_ra', 'False')

    with StringIO() as buf:
        config.write(buf)
        buf.seek(0)

        return buf.read().encode()


def _write_ipa_file(ipa_path: IPAPath, data: bytes) -> None:
    with NamedTemporaryFile(dir=IPAPath.IPADIR.path, delete=False) as f:
        f.write(data)
        f.flush()
        os.rename(f.name, ipa_path.path)
        os.fchmod(f.fileno(), ipa_path.perm)
        if not os.path.exists(ipa_path.path):
            raise RuntimeError(f'{ipa_path.path}: failed to create file')

        return ipa_path.path


def write_ipa_default_config(
    host: str,
    domain: str,
    realm: str,
    server: str
) -> None:
    """
    Write the freeipa default.conf file based on the specified arguments
    """
    config = generate_ipa_default_config(host, domain, realm, server)
    return _write_ipa_file(IPAPath.DEFAULTCONF, config)


def write_ipa_cacert(cacert_bytes):
    return _write_ipa_file(IPAPath.CACERT, cacert_bytes)

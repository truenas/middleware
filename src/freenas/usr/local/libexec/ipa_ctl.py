#!/usr/bin/python3

# IPA control script for TrueNAS IPA Client. This provides support for some
# basic IPA-related operations that the TrueNAS middleware performs.
#
# Although it is written as a standalone script, it is not intended for use
# outside of the scope of TrueNAS developers. Ad-hoc usage of this script may
# result in undefined sever behavior and is not supported in any way.

import argparse
import base64
import json
import subprocess
import sys

from configparser import RawConfigParser
from contextlib import contextmanager
from cryptography.hazmat.primitives.serialization import Encoding
from ipaclient.install.client import get_ca_certs_from_ldap
from ipaclient.install.ipa_client_samba import (
    generate_smb_machine_account,
    retrieve_domain_information,
)
from ipalib import api, errors
from ipapython.ipautil import realm_to_suffix
from ipaplatform.paths import paths
from tempfile import NamedTemporaryFile
from typing import Optional
from middlewared.utils.directoryservices.ipactl_constants import (
    ExitCode,
    IpaOperation,
)
from middlewared.utils.directoryservices.krb5 import KRB5_KT_VNO
from middlewared.utils.directoryservices.krb5_constants import KRB_ETYPE
from middlewared.plugins.smb_.util_param import smbconf_getparm

DESCRIPTION = (
    "This program is intended for exclusive use by TrueNAS developers. "
    "Any use of it outside of the scope of TrueNAS backend operations is "
    "unsupported and may result in a production outage. "
    "This program provides support for some basic FreeIPA server related "
    "operations. "
    "NOTE: requires the following: "
    "(1) valid kerberos ticket and configuration for FreeIPA domain, "
    "(2) valid FreeIPA domain configuration in `/etc/ipa/default.conf`, "
    "(3) valid FreeIPA domain CA certificate in `/etc/ipa/ca.crt`"
)

SUPPORTED_SERVICES = ('cifs', 'nfs')

IPA_JOIN = '/sbin/ipa-join'
IPA_JOIN_CMD_ERR_CODE = {
    0: 'Success',
    1: 'Kerberos context initialization failed',
    2: 'Incorrect usage',
    3: 'Out of memory',
    4: 'Invalid service principal name',
    5: 'No Kerberos credentials cache',
    6: 'No Kerberos principal and no bind DN and password',
    7: 'Failed to open keytab',
    8: 'Failed to create key material',
    9: 'Setting keytab failed',
    10: 'Bind password required when using a bind DN',
    11: 'Failed to add key to keytab',
    12: 'Failed to close keytab',
    13: 'Host is already enrolled',
    14: 'LDAP failure',
    15: 'Incorrect bulk password',
    16: 'Host name must be fully-qualified',
    17: 'RPC fault',
    18: 'Principal not found in host entry',
    19: 'Unable to generate Kerberos credentials cache',
    20: 'Unenrollment result not in RPC response',
    21: 'Failed to get default Kerberos realm',
    22: 'Unable to auto-detect fully-qualified hostname'
}

IPA_GETKEYTAB = '/sbin/ipa-getkeytab'
IPA_GETKEYTAB_ERR_CODE = {
    0: 'Success',
    1: 'Kerberos context initialization failed',
    2: 'Incorrect usage',
    3: 'Out of memory',
    4: 'Invalid service principal name',
    5: 'No Kerberos credentials cache',
    6: 'No Kerberos principal and no bind DN and password',
    7: 'Failed to open keytab',
    8: 'Failed to create key material',
    9: 'Setting keytab failed',
    10: 'Bind password required when using a bind DN',
    11: 'Failed to add key to keytab',
    12: 'Failed to close keytab',
}

DESIRED_ETYPES = (
    KRB_ETYPE.AES256_CTS_HMAC_SHA1_96.value,
    KRB_ETYPE.AES128_CTS_HMAC_SHA1_96.value
)


class IpaCtlError(Exception):
    def __init__(
        self,
        op,
        error_code,
        rpc_response=None,
        text=None,
        error_code_map=None
    ):
        self.error_code = error_code
        self.error_code_str = None
        self.op = op
        self.rpc_response = rpc_response
        self.text = text.strip()
        self.errmsg = self.__get_errmsg(error_code_map)

    def __get_errmsg(self, error_code_map):
        if self.rpc_response:
            return json.dumps(self.rpc_response)

        if self.text:
            return self.text

        if error_code_map:
            return error_code_map.get(self.error_code)

        return f'Operation failed with unknown error: {self.error_code}'

    def __str__(self):
        return f'[{self.op}]: {self.errmsg}'


@contextmanager
def temporary_keytab():
    """
    This is a simple context manager for a temporary keytab that is deleted
    when it exits. The purpose is to provide a target for keytab writes from
    various tools before we convert data to base64 and include in response to
    caller.
    """
    with NamedTemporaryFile() as fname:
        fname.write(KRB5_KT_VNO)
        fname.flush()

        yield fname


def extract_json_rpc_msg(data):
    """
    ipa-join, ipa-getkeytab, and ipa-rmkeytab print JSON-RPC request and response
    information to stderr when the debug flag is passed `-d`. By the time this
    is called, we've already confirmed that `JSON-RPC response:' is in `data`.
    """
    json_msg = data.split('JSON-RPC response:')[1].strip().splitlines()[0].strip()
    return json.loads(json_msg)


def raise_ipa_cmd_failure(op, exit_code, errmsg, error_code_map):
    # If we got as far as to communicate with FreeIPA, present the
    # JSON-RPC response to the caller, otherwise dump as-is.
    if 'JSON-RPC response' not in errmsg:
        raise IpaCtlError(op, exit_code, text=errmsg, error_code_map=error_code_map)

    raise IpaCtlError(op, exit_code, rpc_response=extract_json_rpc_msg(errmsg))


def initialize_ipa_connection():
    # Set IPA context that will be used for access then perform client
    # connection.
    #
    # NOTE: this requires valid kerberos ticket.
    api.bootstrap(context="custom", in_server=False)
    api.finalize()
    api.Backend.rpcclient.connect()


def collapse_key(entry, key):
    if entry.get(key) is None:
        return None
    elif isinstance(entry[key], tuple):
        return entry[key][0]

    return entry[key]


def parse_ldap_result(entry):
    output = {}
    for key in entry.keys():
        output[key] = collapse_key(entry, key)

    return output


def add_service(hostname: str, service_name: str):
    res = api.Command.service_add(f'{service_name}/{hostname}')
    return res['value']


def del_service(hostname: str, service_name: str):
    res = api.Command.service_del(f'{service_name}/{hostname}')
    return {'service': res['value'][0]}


def del_service_smb(hostname: str, realm: str):
    principal = f'cifs/{hostname}@{realm}'
    res = api.Command.service_del(principal)
    return res['value']


def get_keytab(
    principal_name: str,
    server_name: Optional[str] = None,
    get_password: Optional[bool] = False
) -> str:
    """
    Generate a keytab for the specified `principal_name`

    param: server_name - optionally specify name of FreeIPA server for operation.

    get_password: set password in kerberos keytab to randomized string and include
    both keytab and password in output.

    returns: dictionary containing base64-encoded keytab and optionally password.

    WARNING: this invalidates existing keytab for service
    """
    if get_password:
        # generate a randomized password with ascii characters
        # with minimum length of 128 and maximum of 256
        password = generate_smb_machine_account(None, None, None, None)

    with temporary_keytab() as fname:
        etypes = list(DESIRED_ETYPES)
        if principal_name.startswith('cifs'):
            # SMB service must have arcfour-hmac generated to allow domain
            # member to authenticate to domain controller.
            etypes.append(KRB_ETYPE.ARCFOUR_HMAC.value)

        cmd = [
            IPA_GETKEYTAB,
            '-p', principal_name,
            '-k', fname.name,
            '-e', ','.join(etypes)
        ]
        if server_name:
            cmd.extend([
                '-s', server_name
            ])

        if get_password:
            cmd.append('-P')
            res = subprocess.run(
                cmd, check=False,
                input=b'{password}\n{password}',
                capture_output=True
            )
        else:
            res = subprocess.run(cmd, check=False, capture_output=True)

        if res.returncode:
            raise_ipa_cmd_failure(
                'IPA-GETKEYTAB',
                res.returncode,
                res.stderr.decode(),
                IPA_GETKEYTAB_ERR_CODE
            )

        with open(fname.name, 'rb') as f:
            kt = base64.b64encode(f.read())

        if get_password:
            return {'keytab': kt.decode(), 'password': password}
        else:
            return {'keytab': kt.decode()}


def get_smb_service_keytab_and_password(hostname: str, realm: str):
    """
    Generate a kerberos keytab and password for the SMB service for the
    specified hostname + realm. The password is returned so that may be
    inserted by caller into samba's secrets.tdb
    """
    principal = f'cifs/{hostname}@{realm}'
    try:
        api.Command.service_show(principal)

        api.Command.service_del(principal)
    except errors.NotFound:
        pass

    netbiosname = smbconf_getparm('netbiosname')
    api.Command.service_add_smb(hostname, netbiosname)

    kt_resp = get_keytab(principal, get_password=True)
    api.Command.service_mod(principal, addattr='ipaNTHash=MagicRegen')

    return kt_resp | {'service': principal}


def get_service_keytab(hostname, service, force=False):
    """
    Get a base64-encoded kerberos keytab for the specified
    service name for the specified hostname.

    return dictionary as follows:
    ```
    {
      "keytab": <base64 string>,
      "service": "nfs"
    }
    ```
    """
    try:
        entry = api.Command.service_show(f'{service}/{hostname}')['result']
    except errors.NotFound:
        add_service(hostname, service)
        entry = api.Command.service_show(f'{service}/{hostname}')['result']

    principal = parse_ldap_result(entry)['krbprincipalname']
    return get_keytab(principal) | {'service': principal}


def get_ipa_cacerts(server, realm):
    base_dn = str(realm_to_suffix(realm))
    cert_bytes = b''
    certs = get_ca_certs_from_ldap(server, base_dn, realm)
    for cert in certs:
        cert_bytes += cert.public_bytes(Encoding.PEM)

    return {'realm': realm, 'cacert': cert_bytes.decode()}


def has_ticket_assert():
    rv = subprocess.run(['klist', '-s'], check=False)
    if rv.returncode != 0:
        print('Kerberos ticket is required', file=sys.stderr)
        sys.exit(ExitCode.KERBEROS)


def parse_ipa_config():
    parser = RawConfigParser()
    try:
        parser.read(paths.IPA_DEFAULT_CONF)
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(ExitCode.FREEIPA_CONFIG)

    return parser


def ipa_join(
    hostname: str,
    ipa_server: str,
    realm: str,
):
    """
    Join the server to the FreeIPA domain

    param: hostname - fqdn of host joining freeipa 'truenas.testdom.test'

    param: ipa_server - name of target freeipa server 'ipa.testdom.test'

    param: realm - name of kerberos realm of freeipa domain 'TESTDOM.TEST'

    returns: dictionary containing JSON-RPC response and base64-encoded
    keytab for kerberos principal `host/<hostname>`
    """
    base_dn = str(realm_to_suffix(realm))

    with temporary_keytab() as fname:
        join_cmd = [
            IPA_JOIN,
            '-d',
            '-h', hostname,
            '-s', ipa_server,
            '-b', base_dn,
            '-k', fname.name,
        ]
        join = subprocess.run(join_cmd, check=False, capture_output=True)
        match join.returncode:
            case 0:
                # success
                pass
            case 13:
                # server is already enrolled and so we can simply generate new
                # keytab
                resp = get_keytab(f'host/{hostname}', ipa_server)
                json_msg = extract_json_rpc_msg(join.stderr.decode())
                return resp | json_msg
            case _:
                raise_ipa_cmd_failure(
                    'IPA-JOIN',
                    join.returncode,
                    join.stderr.decode(),
                    IPA_JOIN_CMD_ERR_CODE
                )

        with open(fname.name, 'rb') as f:
            kt = base64.b64encode(f.read())

        json_msg = extract_json_rpc_msg(join.stderr.decode())
        return {
            'keytab': kt.decode(),
            'rpc_response': json_msg
        }


def ipa_leave(
    hostname: str,
    ipa_server: str,
    realm: str,
):
    """
    Deactivate the host account associated with `hostname` in FreeIPA.

    param: hostname - fqdn of host joining freeipa 'truenas.testdom.test'

    param: ipa_server - name of target freeipa server 'ipa.testdom.test'

    param: realm - name of kerberos realm of freeipa domain 'TESTDOM.TEST'

    returns: dictionary containing JSON-RPC response

    NOTE: this may fail if additional SPNs are specified for the hostname.
    """
    base_dn = str(realm_to_suffix(realm))

    leave_cmd = [
        IPA_JOIN,
        '-d', '-f',
        '-h', hostname,
        '-s', ipa_server,
        '-b', base_dn,
    ]
    leave = subprocess.run(leave_cmd, check=False, capture_output=True)
    if leave.returncode != 0:
        raise_ipa_cmd_failure(
            'IPA-LEAVE',
            leave.returncode,
            leave.stderr.decode(),
            IPA_JOIN_CMD_ERR_CODE
        )

    json_msg = extract_json_rpc_msg(leave.stderr.decode())
    return {'rpc_response': json_msg}


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument(
        '-a', '--action',
        help='Action to perform related to FreeIPA domain',
        required=True,
        choices=[op.name for op in IpaOperation]
    )
    args = parser.parse_args()

    has_ticket_assert()
    ipa_config = parse_ipa_config()

    initialize_ipa_connection()
    resp = None

    try:
        match args.action:
            case IpaOperation.JOIN.name:
                resp = ipa_join(
                    ipa_config.get('global', 'host'),
                    ipa_config.get('global', 'server'),
                    ipa_config.get('global', 'realm')
                )
            case IpaOperation.LEAVE.name:
                resp = ipa_leave(
                    ipa_config.get('global', 'host'),
                    ipa_config.get('global', 'server'),
                    ipa_config.get('global', 'realm')
                )
            case IpaOperation.SET_NFS_PRINCIPAL.name:
                """
                resp is formatted as follows:

                ```
                {
                  "keytab": <base64 string>,
                  "service": "nfs/truenas.walkerdom.test@WALKERDOM.TEST"
                }
                ```
                """
                resp = get_service_keytab(
                    ipa_config.get('global', 'host'),
                    'nfs'
                )
            case IpaOperation.DEL_NFS_PRINCIPAL.name:
                """
                resp is formatted as follows:

                ```
                {
                  "service": "nfs/truenas.walkerdom.test@WALKERDOM.TEST"
                }
                ```
                """
                resp = del_service(
                    ipa_config.get('global', 'host'), 'nfs'
                )
            case IpaOperation.SET_SMB_PRINCIPAL.name:
                """
                resp is formatted as follows:

                ```
                {
                  "keytab": <base64 string>,
                  "password": <random string>,
                  "domain_info": [
                    {
                      "netbios_name": "WALKERDOM",
                      "domain_sid": "S-1-5-21-3696504179-2855309571-923743039",
                      "domain_name": "walkerdom.test",
                      "range_id_min": 565200000,
                      "range_id_max": 565399999
                    }
                  ],
                  "service": "cifs/truenas.walkerdom.test@WALKERDOM.TEST"
                }
                ```
                """
                if not (domain_info := retrieve_domain_information(api)):
                    print(
                        'No configured trust controller detected '
                        'on IPA masters.',
                        file=sys.stderr
                    )
                    sys.exit(ExitCode.NO_SMB_SUPPORT)
                resp = get_smb_service_keytab_and_password(
                    ipa_config.get('global', 'host'),
                    ipa_config.get('global', 'realm')
                )
                resp |= {'domain_info': domain_info}
            case IpaOperation.DEL_SMB_PRINCIPAL.name:
                resp = del_service_smb(
                    ipa_config.get('global', 'host'),
                    ipa_config.get('global', 'realm')
                )
            case IpaOperation.SMB_DOMAIN_INFO.name:
                resp = retrieve_domain_information(api)
            case IpaOperation.GET_CACERT_FROM_LDAP.name:
                resp = get_ipa_cacerts(
                    ipa_config.get('global', 'server'),
                    ipa_config.get('global', 'realm')
                )
            case _:
                raise ValueError(f'{args.action}: unhandled action')
    except IpaCtlError as e:
        if resp:
            # We may have partially completed request
            # print to stdout so that caller has some
            # chance of error handling
            print(json.dumps(resp))

        if e.rpc_resp:
            print(json.dumps(e.rpc_resp), file=sys.stderr)
            sys.exit(ExitCode.JSON_ERROR)

        sys.exit(ExitCode.GENERIC)
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(ExitCode.GENERIC)

    print(json.dumps(resp))
    sys.exit(ExitCode.SUCCESS)


if __name__ == '__main__':
    main()

# This is a collection of utilities related to kerberos tickets
# and keytabs.
#
# Tests that do not require access to an actual KDC are provided
# in src/middlewared/middlewared/pytest/unit/utils/test_krb5.py
#
# Tests that require access to a KDC are provided as part of API
# test suite.

import errno
import gssapi
import os
import subprocess
import time

from contextlib import contextmanager
from .krb5_constants import krb_tkt_flag, krb5ccache, KRB_ETYPE, KRB_Keytab
from middlewared.service_exception import CallError
from middlewared.utils import filter_list, MIDDLEWARE_RUN_DIR
from middlewared.utils.io import write_if_changed
from tempfile import NamedTemporaryFile
from time import monotonic
from typing import Optional

# See lib/krb5/keytab/kt_file.c in MIT kerberos source
KRB5_KT_VNO = b'\x05\x02'  # KRB v5 keytab version 2, (last changed in 2009)

# Some environments may have very slow replication between KDCs. When we first join
# we need to lock in the KDC we used to join for a period of time

SAF_CACHE_TIMEOUT = 3600  # 1 hour
SAF_CACHE_FILE = os.path.join(MIDDLEWARE_RUN_DIR, '.KDC_SERVER_AFFINITY')


# The following schemas are used for validation of klist / ktutil_list output
KLIST_ENTRY_SCHEMA = {
    'type': 'object',
    'properties': {
        'issued': {'type': 'integer'},
        'expires': {'type': 'integer'},
        'renew_until': {'type': 'integer'},
        'client': {'type': 'string'},
        'server': {'type': 'string'},
        'etype': {'type': 'string'},
        'flags': {
            'type': 'array',
            'items': {
                'type': 'string',
                'enum': [k.name for k in krb_tkt_flag],
                'uniqueItems': True
            }
        }
    },
    'required': [
        'issued', 'expires', 'renew_until',
        'client', 'server', 'etype', 'flags'
    ],
    'additionalProperties': False
}

KLIST_OUTPUT_SCHEMA = {
    'type': 'object',
    'properties': {
        'default_principal': {'type': 'string'},
        'ticket_cache': {
            'type': 'object',
            'properties': {
                'type': {'type': 'string'},
                'name': {'type': 'string'}
            },
            'required': ['type', 'name']
        },
        'tickets': {
            'type': 'array',
            'items': KLIST_ENTRY_SCHEMA,
            'uniqueItems': True
        },
    },
    'required': ['default_principal', 'ticket_cache', 'tickets']
}

KTUTIL_LIST_ENTRY_SCHEMA = {
    'type': 'object',
    'properties': {
        'slot': {'type': 'integer'},
        'kvno': {'type': 'integer'},
        'principal': {'type': 'string'},
        'etype': {
            'type': 'string',
            'enum': [k.value for k in KRB_ETYPE],
            'uniqueItems': True
        },
        'etype_deprecated': {'type': 'boolean'},
        'date': {'type': 'integer'},
    },
    'required': [
        'slot', 'kvno', 'etype', 'etype_deprecated', 'date'
    ],
    'additionalProperties': False
}

KTUTIL_LIST_OUTPUT_SCHEMA = {
    'type': 'array',
    'items': KTUTIL_LIST_ENTRY_SCHEMA,
    'uniqueItems': True
}


def __tmp_krb5_keytab() -> str:
    """
    Create a temporary keytab file with appropriate header
    """
    with NamedTemporaryFile(delete=False) as tmpfile:
        tmpfile.write(KRB5_KT_VNO)
        tmpfile.flush()
        tmpfile.close()

        return tmpfile.name


@contextmanager
def temporary_keytab():
    kt = __tmp_krb5_keytab()
    try:
        yield kt
    finally:
        os.remove(kt)


def parse_klist_output(klistbuf: str) -> list:
    """
    This is an internal method that parses the output of `klist -ef`
    """
    tickets = klistbuf.splitlines()

    ticket_cache = None
    default_principal = None
    tlen = len(tickets)

    parsed_klist = []
    for idx, e in enumerate(tickets):
        if e.startswith('Ticket cache'):
            cache_type, cache_name = e.strip('Ticket cache: ').split(':', 1)
            ticket_cache = {
                'type': cache_type,
                'name': cache_name.strip()
            }

        if e.startswith('Default'):
            default_principal = (e.split(':')[1]).strip()
            continue

        if e and e[0].isdigit():
            d = e.split("  ")
            issued = int(time.mktime(time.strptime(d[0], "%m/%d/%y %H:%M:%S")))
            expires = int(time.mktime(time.strptime(d[1], "%m/%d/%y %H:%M:%S")))
            client = default_principal
            server = d[2]
            renew_until = 0
            flags = ''
            etype = None

            for i in range(idx + 1, idx + 3):
                if i >= tlen:
                    break
                if tickets[i][0].isdigit():
                    break
                if tickets[i].startswith("\tEtype"):
                    etype = tickets[i].strip()
                    break

                if tickets[i].startswith("\trenew"):
                    ts, flags = tickets[i].split(",")
                    renew_until = int(time.mktime(time.strptime(
                        ts.strip('\trenew until '), "%m/%d/%y %H:%M:%S"
                    )))
                    flags = flags.split("Flags: ")[1]
                    continue

                extra = tickets[i].split(", ", 1)
                flags = extra[0][7:].strip()
                etype = extra[1].strip()

            parsed_klist.append({
                'issued': issued,
                'expires': expires,
                'renew_until': renew_until,
                'client': client,
                'server': server,
                'etype': etype,
                'flags': [krb_tkt_flag(f).name for f in flags],
            })

    return {
        'default_principal': default_principal,
        'ticket_cache': ticket_cache,
        'tickets': parsed_klist,
    }


def klist_impl(ccache_path: str) -> list:
    kl = subprocess.run(['klist', '-ef', ccache_path], capture_output=True)
    return parse_klist_output(kl.stdout.decode())


def gss_acquire_cred_user(
    username: str,
    password: str,
    ccache_path: str | None = None,
    lifetime: int | None = None
) -> gssapi.Credentials:
    """
    Acquire GSSAPI credentials based on provided username + password combination
    This relies on krb5.conf being properly configured for the kerberos realm.

    If `ccache_path` is specified then the credentials are also written to the
    specified ccache.

    `lifetime` (seconds) may be used to override the defaults in krb5.conf.

    Returns gssapi.Credentials

    Raises:
        gssapi.exceptions.MissingCredentialsError -- may be converted to KRBError
        gssapi.exceptions.BadNameError -- user supplied invalid username
    """
    gss_name = gssapi.raw.import_name(username.encode(), gssapi.NameType.user)
    cr = gssapi.raw.acquire_cred_with_password(
        gss_name, password.encode(), lifetime=lifetime
    )

    if ccache_path is not None:
        gssapi.raw.store_cred_into(
            {'ccache': ccache_path},
            cr.creds,
            usage='initiate',
            mech=gssapi.raw.MechType.kerberos,
            set_default=True, overwrite=True
        )

    return gssapi.Credentials(cr.creds)


def gss_acquire_cred_principal(
    principal_name: str,
    ccache_path: str | None = None,
    lifetime: int | None = None,
) -> gssapi.Credentials:
    """
    Acquire GSSAPI credentials based on provided specified kerberos principal
    name. This relies on krb5.conf being properly configured for the kerberos realm,
    /etc/krb5.keytab existing and it having an entry that matches the princpal name.

    If `ccache_path` is specified then the credentials are also written to the
    specified ccache.

    `lifetime` (seconds) may be used to override the defaults in krb5.conf.

    Returns gssapi.Credentials

    Raises:
        gssapi.exceptions.MissingCredentialsError -- may be converted to KRBError
        gssapi.exceptions.BadNameError -- user supplied invalid kerberos principal name
    """
    gss_name = gssapi.Name(principal_name, gssapi.NameType.kerberos_principal)
    store = {'client_keytab': KRB_Keytab.SYSTEM.value}
    if ccache_path is not None:
        store['ccache'] = ccache_path

    cr = gssapi.Credentials(
        name=gss_name,
        store=store,
        usage='initiate',
        lifetime=lifetime,
    )

    if ccache_path is not None:
        cr.store(set_default=True, overwrite=True)

    return cr


def gss_get_current_cred(
    ccache_path: str,
    raise_error: Optional[bool] = True
) -> gssapi.Credentials | None:
    """
    Use gssapi library to inpsect the ticket in the specified ccache

    Returns gssapi.Credentials and optionally (if raise_error is False)
    None.
    """
    try:
        cred = gssapi.Credentials(store={'ccache': ccache_path}, usage='initiate')
    except gssapi.exceptions.MissingCredentialsError:
        if not raise_error:
            return None

        raise CallError(f'{ccache_path}: Credentials cache does not exist', errno.ENOENT)

    try:
        cred.inquire()
    except gssapi.exceptions.InvalidCredentialsError as e:
        if not raise_error:
            return None

        raise CallError(str(e))

    except gssapi.exceptions.ExpiredCredentialsError:
        if not raise_error:
            return None

        raise CallError('Kerberos ticket is expired', errno.ENOKEY)

    except Exception as e:
        if not raise_error:
            return None

        raise CallError(str(e))

    return cred


def gss_dump_cred(cred: gssapi.Credentials) -> dict:
    if not isinstance(cred, gssapi.Credentials):
        raise TypeError(f'{type(cred)}: not gssapi.Credentials type')

    match cred.name.name_type:
        case gssapi.NameType.user:
            name_type_str = 'USER'
        case gssapi.NameType.kerberos_principal:
            name_type_str = 'KERBEROS_PRINCIPAL'
        case _:
            # We only expect to have USER and KERBEROS principals
            # we'll dump the OID
            name_type_str = f'UNEXPECTED NAME TYPE: {cred.name.name_type}'

    return {
        'name': str(cred.name),
        'name_type': name_type_str,
        'name_type_oid': cred.name.name_type.dotted_form,
        'lifetime': cred.lifetime,
    }


def kerberos_ticket(fn):
    """ Decorator to raise a CallError if no ccache or if ticket in ccache is expired """
    def check_ticket(*args, **kwargs):
        gss_get_current_cred(krb5ccache.SYSTEM.value)
        return fn(*args, **kwargs)

    return check_ticket


def parse_keytab(keytab_output: list) -> list:
    """
    Internal parser for output of `klist -ket` for a kerberos keytab
    """
    keytab_entries = []

    for idx, line in enumerate(keytab_output):
        fields = line.split()
        keytab_entries.append({
            'slot': idx + 1,
            'kvno': int(fields[0]),
            'principal': fields[3],
            'etype': fields[4][1:-1].strip('DEPRECATED:'),
            'etype_deprecated': fields[4][1:].startswith('DEPRECATED'),
            'date': int(time.mktime(time.strptime(fields[1], '%m/%d/%y'))),
        })

    return keytab_entries


def ktutil_list_impl(keytab_file: str = KRB_Keytab.SYSTEM.value) -> list:
    """
    Thin wrapper around `klist -ket` that returns keytab entries as a list

    `keytab_file` - path to kerberos keytab
    """
    kt_output = subprocess.run(
        ['klist', '-ket', keytab_file],
        capture_output=True
    )

    kt_lines = kt_output.stdout.decode().splitlines()
    if len(kt_lines) < 4:
        # we only have header
        return []

    return parse_keytab(kt_lines[3:])


def keytab_services(keytab_file: str) -> list:
    """
    Return list of service names provided by keytab

    `keytab_file` - path to kerberos keytab
    """
    keytab_data = filter_list(
        ktutil_list_impl(keytab_file),
        [['principal', 'rin', '/']]
    )
    services = []
    for entry in keytab_data:
        services.append(entry['principal'].split('/')[0])

    return services


def extract_from_keytab(
    keytab_file: str,
    filters: list
) -> bytes:
    """
    Extract keytab entries matching filter and return as bytes

    `keytab_file` - path to kerberos keytab
    `filters` - query-filters
    """
    kt_list = ktutil_list_impl(keytab_file)
    to_keep = filter_list(kt_list, filters)
    to_remove = [entry['slot'] for entry in kt_list if entry not in to_keep]

    if len(kt_list) == len(to_remove):
        # Let caller know that keytab would be empty. If we were to follow
        # through with this, caller would receive # keytab containing only
        # `b'\x05\x02' (KRB5_KT_VNO)`
        return None

    tmp_keytab = __tmp_krb5_keytab()

    rkt = f'rkt {keytab_file}'
    wkt = f'wkt {tmp_keytab}'

    delents = "\n".join(f'delent {slot}' for slot in reversed(to_remove))

    ktutil_op = subprocess.run(
        ['ktutil'],
        input=f'{rkt}\n{delents}\n{wkt}\n'.encode(),
        check=False, capture_output=True
    )

    # ktutil does not set returncode for malformed
    # commands or commands that otherwise fail
    if ktutil_op.returncode or ktutil_op.stderr:
        os.remove(tmp_keytab)
        raise RuntimeError(ktutil_op.stderr.decode())

    if len(ktutil_list_impl(tmp_keytab)) != len(to_keep):
        raise RuntimeError('Temporary keytab did not contain correct number of entries')

    with open(tmp_keytab, 'rb') as f:
        kt_bytes = f.read()

    os.remove(tmp_keytab)
    return kt_bytes


def concatenate_keytab_data(keytab_data: list[bytes]) -> bytes:
    """
    Concatenate a list of keytab bytes into a single kerbros keytab.
    We base64 encode keytabs stored in the our config file, which means
    the should be decoded prior to generating the list passed to this
    function as an argument.
    """

    # First create temporary keytab that will hold the unified keytab data
    with temporary_keytab() as unified:
        for data in keytab_data:
            # then write each keytab in the list to temporary files
            with temporary_keytab() as kt:
                with open(kt, 'wb') as f:
                    f.write(data)
                    f.flush()

                # then copy from the keytab data to the destination by having
                # ktutil read the data, then write it. This validates that
                # the data is actually a keberos keytab.
                kt_copy = subprocess.run(
                    ['ktutil'],
                    input=f'rkt {kt}\nwkt {unified}'.encode(),
                    capture_output=True
                )
                if kt_copy.stderr:
                    raise RuntimeError('Failed to concatenate keytabs: %s',
                                       kt_copy.stderr.decode())

        # get bytes of the unified keytab before allowing contextmanager
        # to delete it
        with open(unified, 'rb') as f:
            return f.read()


def middleware_ccache_uid(data: dict) -> int:
    cc_uid = data.get('ccache_uid', 0)
    if not isinstance(cc_uid, int):
        raise TypeError(f'{type(cc_uid)}: expected ccache_uid to be an int')

    return cc_uid


def middleware_ccache_type(data: dict) -> krb5ccache:
    cc = data.get('ccache', krb5ccache.SYSTEM.name)
    if not isinstance(cc, str):
        raise TypeError(f'{type(cc)}: expected ccache to be string')

    return krb5ccache[cc]


def middleware_ccache_path(data: dict) -> str:
    """
    Historically there are various places in the API where parameters related
    to the kerberos credential path could be included in a python dictionary

    This function replaces some heavy-lifting that the legacy schema was
    performing to convert this payload into a path for the kerberos
    credential cache.
    """
    krb_ccache = middleware_ccache_type(data)
    cc_uid = middleware_ccache_uid(data)
    ccache_path = krb_ccache.value

    if krb_ccache is krb5ccache.USER:
        ccache_path += str(cc_uid)

    return ccache_path


def kdc_saf_cache_get() -> str | None:
    try:
        with open(SAF_CACHE_FILE, 'r') as f:
            kdc, timeout = f.read().split()
            if monotonic() > int(timeout.strip()):
                # Expired
                return None

            return kdc.strip()
    except FileNotFoundError:
        return None


def kdc_saf_cache_set(kdc: str) -> None:
    if not isinstance(kdc, str):
        raise TypeError(f'{kdc}: not a string')
    write_if_changed(SAF_CACHE_FILE, f'{kdc} {int(monotonic()) + SAF_CACHE_TIMEOUT}')

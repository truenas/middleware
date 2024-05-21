# This is a collection of utilities related to kerberos tickets
# and keytabs.
#
# Tests that do not require access to an actual KDC are provided
# in src/middlewared/middlewared/pytest/unit/utils/test_krb5.py
#
# Tests that require access to a KDC are provided as part of API
# test suite.

import os
import subprocess
import time

from .krb5_constants import krb_tkt_flag, KRB_ETYPE
from middlewared.utils import filter_list
from tempfile import NamedTemporaryFile

# See lib/krb5/keytab/kt_file.c in MIT kerberos source
KRB5_KT_VNO = b'\x05\x02'  # KRB v5 keytab version 2, (last changed in 2009)

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
    tmpfile = NamedTemporaryFile(delete=False)
    with NamedTemporaryFile(delete=False) as tmpfile:
        tmpfile.write(KRB5_KT_VNO)
        tmpfile.flush()
        tmpfile.close()

        return tmpfile.name


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


def ktutil_list_impl(keytab_file: str) -> list:
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
        # `b'\x05\x02'`
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

    with open(tmp_keytab, 'rb') as f:
        kt_bytes = f.read()

    os.remove(tmp_keytab)
    return kt_bytes

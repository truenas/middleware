import os
import subprocess
import time

from .constants import krb5ccache, krb_tkt_flag, KRB_ETYPE
from middlewared.utils import filter_list
from tempfile import NamedTemporaryFile


REQ_KT_PAYLOAD_ENTRIES = ('password', 'enctypes')
KNOWN_KT_SERVICES = ('host', 'nfs', 'restrictedkrbhost')


def __check_keytab_spec(entry):
    for key in REQ_KT_PAYLOAD_ENTRIES:
        if key not in entry:
            raise ValueError(f'{key}: required key is missing from entry')

    if 'principal' in entry:
        for key in ('service', 'hostname'):
            if key in entry:
                raise ValueError(
                    f'{key}: this may not be specified when providing a full principal name'
                )
    else:
        for key in ('service', 'hostname'):
            if key not in entry:
                raise ValueError(
                    f'{key}: this must be specified if full principal name is not provided.'
                )


def __parse_kvno_resp(output):
    principal, kvno = output.split(':')
    return (principal.strip(), int(kvno.split('=')[1].strip()))


def lookup_kvno_by_principal(principal: str):
    kvno_op = subprocess.run(['kvno', principal], capture_output=True, check=False)
    if kvno_op.returncode:
        err = kvno_op.stderr.decode()
        if 'Server not found in Kerberos database' in err:
            raise FileNotFoundError(f'{principal}: server unknown to remote KDC')

        raise RuntimeError(err)

    return __parse_kvno_resp(kvno_op.stdout.decode())


def lookup_kvno_by_service_and_hostname(
    service: str,
    hostname: str
) -> tuple:
    """
    Retrieve the version number for the kerberos principal from remote
    KDC. If KDC doesn't have an entry for it then there's no point in
    proceeding.
    """
    if service not in KNOWN_KT_SERVICES:
        raise ValueError(f'{service}: unknown service')

    kvno_op = subprocess.run(
        ['kvno', '-S', service, hostname],
        capture_output=True, check=False
    )
    if kvno_op.returncode:
        err = kvno_op.stderr.decode()
        if 'Server not found in Kerberos database' in err:
            raise FileNotFoundError(f'{service}/{hostname}: server unknown to remote KDC')

        raise RuntimeError(err)

    return __parse_kvno_resp(kvno_op.stdout.decode())


def __tmp_krb5_keytab() -> str:
    """
    Create a temporary keytab file with appropriate header
    """
    tmpfile = NamedTemporaryFile(delete=False)
    tmpfile.write(b'\x05\x02')
    tmpfile.flush()
    tmpfile.close()
    return tmpfile.name


def keytab_from_entries(entries: list) -> bytes:
    """
    Return bytes of keytab file representing specified `entries`.

    Each entry should contain the following keys:
    `password` - password for entry
    `enctypes` - encryption type
    `hostname` - hostname of server
    `service` - service (nfs, host, etc)
    `salt` - salt - if omitted, salt information will be fetched from kdc
    """
    cmd_list = []
    for idx, entry in enumerate(entries):
        __check_keytab_spec(entry)

        if (principal := entry.get('principal')):
            principal, kvno = lookup_kvno_by_principal(principal)
        else:
            principal, kvno = lookup_kvno_by_service_and_hostname(
                entry['service'], entry['hostname']
            )

        for e in entry['enctypes']:
            enctype = KRB_ETYPE[e].value

            # by this point enctype is known to be good
            # as is service, host, and kvno
            cmd = (
                f'addent -password '
                f'-p {principal} -k {kvno} -e {enctype} '
            )
            if entry.get('salt'):
                cmd += f'-s {entry["salt"]}'

            cmd_list.append(cmd)

            # ktutil prompts for password after running above command
            cmd_list.append(entry['password'])

    tmp_keytab = __tmp_krb5_keytab()
    # create a temporary file to hold the keytab
    cmd_list.append(f'wkt {tmp_keytab}')

    # Make sure we quit when done
    cmd_list.append('q')

    ktutil_op = subprocess.run(
        ['ktutil'],
        input='\n'.join(cmd_list).encode(),
        check=False, capture_output=True
    )

    # ktutil does not set returncode for malformed
    # commands or commands that otherwise fail
    if ktutil_op.returncode or ktutil_op.stderr:
        os.remove(tmp_keytab)
        raise RuntimeError(ktutil_op.stderr.decode())

    with open(tmp_keytab, 'rb') as f:
        data = f.read()

    os.remove(tmp_keytab)
    return data


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
            if cache_type == 'FILE':
                cache_name = krb5ccache(cache_name.strip()).name

            ticket_cache = {
                'type': cache_type,
                'name': cache_name
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
                    renew_until = time.mktime(time.strptime(ts.strip('\trenew until '), "%m/%d/%y %H:%M:%S"))
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
            'date': time.mktime(time.strptime(fields[1], '%m/%d/%y')),
        })

    return keytab_entries


def ktutil_list_impl(keytab_file: str) -> list:
    """
    Thin wrapper around `klist -ket` that returns keytab entries as a list
    """
    kt_output = subprocess.run(['klist', '-ket', keytab_file], capture_output=True)

    kt_lines = kt_output.stdout.decode().splitlines()
    if len(kt_lines) < 4:
        # we only have header
        return []

    return parse_keytab(kt_lines[3:])


def extract_from_keytab(
    keytab_file: str,
    filters: list
) -> bytes:
    """
    Extract keytab entries matching filter and return as bytes
    """
    kt_list = ktutil_list_impl(keytab_file)
    to_keep = filter_list(kt_list, filters)
    to_remove = [entry['slot'] for entry in kt_list if entry not in to_keep]
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

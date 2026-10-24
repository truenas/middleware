"""Install-scoped HexOS identity, independent of the four-byte ZFS hostid.

Only the installer and an explicit local administrator action create an identity.
The vendor service never creates, replaces or repairs identity state.
"""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

from middlewared.utils.vendor import Vendors

DATA = Path('/data')
LEGACY_HOSTID = Path('/etc/hostid')
NAMESPACE = 'hexos-identity'
RECORD = 'identity.json'
OWNER_UID = 0
MAX_RECORD_BYTES = 4096
MIDDLEWARE_SOCKETS = (
    Path('/run/middleware/middlewared.sock'),
    Path('/run/middleware/middlewared-internal.sock'),
)
HEXOS_KEY_NAMES = ('HexOS', 'HexOS2', 'HexOS2-pending')


class IdentityError(Exception):
    """Identity state is uncertain; do not select another identity."""


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise IdentityError('The identity record contains duplicate fields')
        result[key] = value
    return result


def check_owner_mode(info, mode, description):
    if info.st_uid != OWNER_UID or stat.S_IMODE(info.st_mode) != mode:
        raise IdentityError(f'{description} must be owned by root with mode {mode:o}')


@contextmanager
def data_directory(data, *, require_secure=True):
    fd = os.open(data, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if require_secure:
            check_data_directory(os.fstat(fd))
        yield fd
    finally:
        os.close(fd)


def check_data_directory(info):
    if info.st_uid != OWNER_UID or info.st_mode & 0o022:
        raise IdentityError('The data directory must be root-owned and not writable by other users')


def open_namespace(data_fd):
    try:
        fd = os.open(NAMESPACE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=data_fd)
    except FileNotFoundError:
        return None
    try:
        check_owner_mode(os.fstat(fd), 0o700, 'The identity directory')
    except Exception:
        os.close(fd)
        raise
    return fd


def read_record(directory_fd):
    fd = os.open(RECORD, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise IdentityError('The identity record must be a regular file')
        check_owner_mode(info, 0o600, 'The identity record')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(MAX_RECORD_BYTES + 1)
        if len(raw) > MAX_RECORD_BYTES:
            raise IdentityError('The identity record is too large')
        try:
            record = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_fields)
        except (ValueError, RecursionError) as error:
            raise IdentityError('The identity record is not valid JSON') from error
        if (
            not isinstance(record, dict)
            or set(record) != {'version', 'id'}
            or type(record['version']) is not int
            or record['version'] != 1
            or not isinstance(record['id'], str)
            or re.fullmatch('[0-9a-f]{64}', record['id']) is None
        ):
            raise IdentityError('The identity record has an unsupported format')
        return bytes.fromhex(record['id'])
    finally:
        os.close(fd)


def legacy_host_id(path=LEGACY_HOSTID):
    # Preserve the legacy derivation exactly, including any whitespace bytes.
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def selected_identity(data=DATA, legacy=LEGACY_HOSTID):
    """Return (scheme, hostID). Only an absent namespace permits legacy fallback."""
    with data_directory(data, require_secure=False) as data_fd:
        directory_fd = open_namespace(data_fd)
        if directory_fd is None:
            return 'legacy', legacy_host_id(legacy)
        try:
            check_data_directory(os.fstat(data_fd))
            return 'v1', hashlib.sha256(read_record(directory_fd)).hexdigest()
        finally:
            os.close(directory_fd)


def check_create_target(data_fd, allow_empty):
    directory_fd = open_namespace(data_fd)
    if directory_fd is None:
        return
    try:
        if not allow_empty or os.listdir(directory_fd):
            raise IdentityError('An identity directory already exists; it will not be replaced')
    finally:
        os.close(directory_fd)


def create_identity(data=DATA, *, before_publish=None, allow_empty=False):
    """Publish a complete new namespace. Never replace an existing nonempty one."""
    with data_directory(data) as data_fd:
        check_create_target(data_fd, allow_empty)
        identity = os.urandom(32)
        if len(identity) != 32:
            raise IdentityError('The random source did not return a complete identity')
        stage = Path(tempfile.mkdtemp(prefix='.hexos-identity-', dir=data))
        os.chmod(stage, 0o700)
        published = False
        try:
            payload = (json.dumps({'version': 1, 'id': identity.hex()}) + '\n').encode()
            fd = os.open(stage / RECORD, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, 'wb', closefd=False) as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(fd)
            finally:
                os.close(fd)
            stage_fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(stage_fd)
            finally:
                os.close(stage_fd)
            if before_publish is not None:
                before_publish()
            check_create_target(data_fd, allow_empty)
            os.rename(stage.name, NAMESPACE, src_dir_fd=data_fd, dst_dir_fd=data_fd)
            published = True
            os.fsync(data_fd)
        finally:
            if not published:
                # Only this invocation's exact staging files belong to us. A stale
                # sibling from an interrupted invocation is ignored, never swept.
                try:
                    (stage / RECORD).unlink(missing_ok=True)
                    stage.rmdir()
                except OSError:
                    pass
        return hashlib.sha256(identity).hexdigest()


def require_hexos(data=DATA):
    with open(data / '.vendor', 'rb') as stream:
        vendor = json.load(stream)
    if not isinstance(vendor, dict) or vendor.get('name') != Vendors.HEXOS.value:
        raise IdentityError('This installation is not branded HexOS')


def middleware_call(method, *args):
    result = subprocess.run(
        ['midclt', 'call', method, *(json.dumps(arg) for arg in args)],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


def require_unprovisioned(call=None):
    if call is None:
        call = middleware_call
    config = call('docker.config')
    if not isinstance(config, dict) or 'pool' not in config:
        raise IdentityError('The Apps configuration could not be verified')
    if config['pool'] is not None:
        status = call('docker.status')
        if not isinstance(status, dict) or status.get('status') != 'RUNNING':
            # app.query returns [] when Docker cannot enumerate installed apps.
            raise IdentityError('Start Apps in TrueNAS before checking the existing installation')
    apps = call('app.query', [['id', '=', 'hexos']], {'select': ['id']})
    keys = call('api_key.query', [['name', 'in', list(HEXOS_KEY_NAMES)]], {'select': ['name']})
    if not isinstance(apps, list) or not isinstance(keys, list):
        raise IdentityError('The existing HexOS installation could not be verified')
    if apps or keys:
        raise IdentityError('HexOS is already provisioned; use the existing server reconnect flow')


def status(data=DATA, legacy=LEGACY_HOSTID):
    scheme, host_id = selected_identity(data, legacy)
    print(f'Selected identity: {scheme} {host_id}')
    if scheme != 'legacy':
        print(f'Legacy reference: {legacy_host_id(legacy)}')
        print('The selected identity is used when the vendor connection is next created.')
    return scheme


def main(argv=None):
    parser = argparse.ArgumentParser(description='Inspect or explicitly create a HexOS installation identity')
    parser.add_argument('command', choices=('status', 'recover', 'install-create'))
    parser.add_argument('--installer', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if os.geteuid() != 0:
            raise IdentityError('Run this command as a local administrator using sudo')
        require_hexos(DATA)
        if args.command == 'status':
            status(DATA, LEGACY_HOSTID)
            return 0
        if args.command == 'install-create':
            if (
                not args.installer
                or not (DATA / 'first-boot').is_file()
                or any(os.path.lexists(path) for path in MIDDLEWARE_SOCKETS)
            ):
                raise IdentityError('Install creation is only available inside a fresh installer target')
            create_identity(DATA)
        else:
            # A valid published identity is immutable, even after provisioning.
            with data_directory(DATA) as data_fd:
                directory_fd = open_namespace(data_fd)
                if directory_fd is not None:
                    try:
                        if os.listdir(directory_fd):
                            read_record(directory_fd)
                            status(DATA, LEGACY_HOSTID)
                            return 0
                    finally:
                        os.close(directory_fd)
            require_unprovisioned()
            create_identity(DATA, before_publish=require_unprovisioned, allow_empty=True)
            status(DATA, LEGACY_HOSTID)
            print('Identity saved. Restart this server using the TrueNAS power menu, then return to HexOS setup.')
        return 0
    except (IdentityError, OSError, ValueError, subprocess.SubprocessError) as error:
        # Do not print middleware responses, API keys or the identity seed.
        detail = str(error) if isinstance(error, IdentityError) else type(error).__name__
        print(f'HexOS identity: {detail}. No existing identity was replaced. '
              'Run truenas-hexos-identity status before retrying.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

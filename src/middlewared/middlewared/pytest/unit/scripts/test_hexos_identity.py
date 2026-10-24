from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import threading

import pytest

from middlewared.scripts import hexos_identity as identity


@pytest.fixture
def target(tmp_path, monkeypatch):
    # Native root smoke runs exercise UID 0; local unit runs retain filesystem
    # ownership checks against their actual owner without requiring sudo.
    monkeypatch.setattr(identity, 'OWNER_UID', os.geteuid())
    data = tmp_path / 'data'
    data.mkdir(mode=0o700)
    legacy = tmp_path / 'hostid'
    legacy.write_bytes(b'\n\x01\x02 ')
    return data, legacy


def record_path(data):
    return data / identity.NAMESPACE / identity.RECORD


def put_record(data, payload):
    namespace = data / identity.NAMESPACE
    namespace.mkdir(mode=0o700, exist_ok=True)
    path = record_path(data)
    path.write_bytes(payload)
    path.chmod(0o600)
    return path


def valid_record():
    return json.dumps({'version': 1, 'id': bytes(range(32)).hex()}).encode()


def test_legacy_raw_bytes_are_preserved_and_reader_never_creates(target):
    data, legacy = target
    before = list(data.iterdir())
    for _ in range(20):
        assert identity.selected_identity(data, legacy) == ('legacy', hashlib.sha256(legacy.read_bytes()).hexdigest())
    assert list(data.iterdir()) == before


def test_strong_hashes_decoded_bytes_not_hex_text(target):
    data, legacy = target
    path = put_record(data, valid_record())
    before = path.stat().st_mtime_ns
    expected = hashlib.sha256(bytes(range(32))).hexdigest()
    assert identity.selected_identity(data, legacy) == ('v1', expected)
    assert expected != hashlib.sha256(bytes(range(32)).hex().encode()).hexdigest()
    assert path.stat().st_mtime_ns == before


@pytest.mark.parametrize('payload', [
    b'', b'{', b'null', b'[]', b'{}', b'\xef\xbb\xbf' + valid_record(),
    b'[' * 2000 + b']' * 2000,
    b'{"version":0,"version":1,"id":"' + b'a' * 64 + b'"}',
    *(json.dumps(value).encode() for value in [
        {'version': True, 'id': 'a' * 64},
        {'version': 1.0, 'id': 'a' * 64},
        {'version': 2, 'id': 'a' * 64},
        {'version': 1, 'id': 'A' * 64},
        {'version': 1, 'id': 'a' * 63},
        {'version': 1, 'id': 'a' * 65},
        {'version': 1, 'id': 'g' * 64},
        {'version': 1, 'id': ['a' * 64]},
        {'version': 1, 'id': 'a' * 64, 'extra': 0},
    ]),
    b' ' * identity.MAX_RECORD_BYTES + valid_record(),
    valid_record() + b' ' * identity.MAX_RECORD_BYTES,
])
def test_invalid_record_never_falls_back(target, payload):
    data, legacy = target
    path = put_record(data, payload)
    with pytest.raises(identity.IdentityError):
        identity.selected_identity(data, legacy)
    assert path.read_bytes() == payload


def test_empty_namespace_is_not_legacy(target):
    data, legacy = target
    (data / identity.NAMESPACE).mkdir(mode=0o700)
    with pytest.raises(FileNotFoundError):
        identity.selected_identity(data, legacy)


@pytest.mark.parametrize('kind', ['namespace-symlink', 'file-symlink', 'directory', 'fifo'])
def test_nonregular_paths_refuse_without_following_or_blocking(target, kind):
    data, legacy = target
    outside = data.parent / 'outside'
    outside.mkdir(mode=0o700)
    source = outside / identity.RECORD
    source.write_bytes(valid_record())
    source.chmod(0o600)
    namespace = data / identity.NAMESPACE
    if kind == 'namespace-symlink':
        namespace.symlink_to(outside, target_is_directory=True)
    else:
        namespace.mkdir(mode=0o700)
        path = record_path(data)
        if kind == 'file-symlink':
            path.symlink_to(source)
        elif kind == 'directory':
            path.mkdir()
        else:
            os.mkfifo(path, 0o600)
    with pytest.raises((identity.IdentityError, OSError)):
        identity.selected_identity(data, legacy)
    assert source.read_bytes() == valid_record()


@pytest.mark.parametrize('part,mode', [('namespace', 0o755), ('file', 0o644), ('file', 0o000)])
def test_wrong_modes_refuse(target, part, mode):
    data, legacy = target
    path = put_record(data, valid_record())
    (path.parent if part == 'namespace' else path).chmod(mode)
    with pytest.raises((identity.IdentityError, PermissionError)):
        identity.selected_identity(data, legacy)


def test_wrong_owner_refuses(target, monkeypatch):
    data, legacy = target
    put_record(data, valid_record())
    monkeypatch.setattr(identity, 'OWNER_UID', os.geteuid() + 1)
    with pytest.raises(identity.IdentityError):
        identity.selected_identity(data, legacy)


def test_fresh_installs_do_not_depend_on_legacy_bytes_clock_or_pid(target, monkeypatch):
    data, legacy = target
    monkeypatch.setattr(os, 'getpid', lambda: 700)
    import time
    monkeypatch.setattr(time, 'time', lambda: 1792800000)
    first = identity.create_identity(data)
    other = data.parent / 'other-data'
    other.mkdir(mode=0o700)
    second = identity.create_identity(other)
    assert first != second
    assert identity.selected_identity(data, legacy) == ('v1', first)
    assert identity.selected_identity(other, legacy) == ('v1', second)
    assert legacy.read_bytes() == b'\n\x01\x02 '
    assert record_path(data).stat().st_mode & 0o777 == 0o600
    assert record_path(data).parent.stat().st_mode & 0o777 == 0o700


def test_existing_identity_is_never_replaced(target):
    data, legacy = target
    original = identity.create_identity(data)
    before = record_path(data).read_bytes()
    for allow_empty in (False, True):
        with pytest.raises(identity.IdentityError):
            identity.create_identity(data, allow_empty=allow_empty)
    assert record_path(data).read_bytes() == before
    assert identity.selected_identity(data, legacy)[1] == original


def test_only_explicit_recovery_completes_a_valid_empty_namespace(target):
    data, legacy = target
    (data / identity.NAMESPACE).mkdir(mode=0o700)
    with pytest.raises(identity.IdentityError):
        identity.create_identity(data)
    expected = identity.create_identity(data, allow_empty=True)
    assert identity.selected_identity(data, legacy) == ('v1', expected)


def test_unrelated_and_stale_files_are_not_removed(target):
    data, _ = target
    stale = data / '.hexos-identity-stale'
    stale.mkdir(mode=0o700)
    (stale / 'keep').write_text('evidence')
    identity.create_identity(data)
    assert (stale / 'keep').read_text() == 'evidence'
    assert len(list(data.iterdir())) == 2


@pytest.mark.parametrize('kind', ['error', 'short'])
def test_entropy_failure_never_publishes_or_falls_back(target, monkeypatch, kind):
    data, _ = target
    def entropy(_size):
        if kind == 'error':
            raise OSError('entropy unavailable')
        return b'x' * 4
    monkeypatch.setattr(os, 'urandom', entropy)
    with pytest.raises((identity.IdentityError, OSError)):
        identity.create_identity(data)
    assert list(data.iterdir()) == []


def test_recovery_final_checks_refuse_before_publication(target):
    data, _ = target
    def refuse():
        raise identity.IdentityError('Provisioning started')
    with pytest.raises(identity.IdentityError):
        identity.create_identity(data, before_publish=refuse)
    assert list(data.iterdir()) == []


def test_concurrent_writers_preserve_one_winner(target):
    data, legacy = target
    barrier = threading.Barrier(2)
    def write():
        try:
            return identity.create_identity(data, before_publish=barrier.wait)
        except (identity.IdentityError, OSError):
            return None
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: write(), range(2)))
    winners = [result for result in results if result is not None]
    assert len(winners) == 1
    assert identity.selected_identity(data, legacy)[1] == winners[0]
    assert len(list(data.iterdir())) == 1


def test_fsync_order_and_failure_after_publish_does_not_rotate(target, monkeypatch):
    data, legacy = target
    original_fsync = os.fsync
    calls = []
    def fsync(fd):
        calls.append(Path(f'/proc/self/fd/{fd}').readlink())
        if len(calls) == 3:
            raise OSError('parent fsync failed')
        original_fsync(fd)
    monkeypatch.setattr(os, 'fsync', fsync)
    with pytest.raises(OSError):
        identity.create_identity(data)
    assert calls[0].name == identity.RECORD
    assert calls[1].name.startswith('.hexos-identity-')
    assert calls[2] == data
    before = identity.selected_identity(data, legacy)
    with pytest.raises(identity.IdentityError):
        identity.create_identity(data)
    assert identity.selected_identity(data, legacy) == before


def test_restrictive_umask_still_produces_readable_private_identity(target):
    data, legacy = target
    old = os.umask(0o777)
    try:
        expected = identity.create_identity(data)
    finally:
        os.umask(old)
    assert identity.selected_identity(data, legacy)[1] == expected


def replies(**overrides):
    values = {'docker.config': {'pool': None}, 'docker.status': {'status': 'RUNNING'},
              'app.query': [], 'api_key.query': []}
    values.update(overrides)
    def call(method, *_args):
        answer = values[method]
        if isinstance(answer, Exception):
            raise answer
        return answer
    return call


def test_recovery_allows_fresh_box_without_apps_pool():
    identity.require_unprovisioned(replies())


@pytest.mark.parametrize('answer', [
    {'app.query': [{'id': 'hexos'}]},
    *({'api_key.query': [{'name': name}]} for name in identity.HEXOS_KEY_NAMES),
    {'docker.config': {}},
    {'docker.config': {'pool': 'apps'}, 'docker.status': {'status': 'STOPPED'}},
    {'docker.config': {'pool': 'apps'}, 'docker.status': {'status': 'FAILED'}},
    {'app.query': None}, {'api_key.query': {}},
    {'app.query': OSError('unavailable')}, {'api_key.query': OSError('unavailable')},
])
def test_unavailable_or_provisioned_state_refuses_recovery(answer):
    with pytest.raises((identity.IdentityError, OSError)):
        identity.require_unprovisioned(replies(**answer))


def test_recovery_accepts_verified_running_apps_without_hexos():
    identity.require_unprovisioned(replies(**{'docker.config': {'pool': 'apps'}}))


@pytest.fixture
def cli(target, monkeypatch):
    data, legacy = target
    monkeypatch.setattr(identity, 'DATA', data)
    monkeypatch.setattr(identity, 'LEGACY_HOSTID', legacy)
    monkeypatch.setattr(identity, 'MIDDLEWARE_SOCKETS', (data.parent / 'middleware.sock',))
    monkeypatch.setattr(os, 'geteuid', lambda: 0)
    (data / '.vendor').write_text('{"name":"HexOS"}')
    return data, legacy


def test_cli_install_requires_explicit_fresh_target(cli):
    data, _ = cli
    assert identity.main(['install-create']) == 1
    assert identity.main(['install-create', '--installer']) == 1
    assert not (data / identity.NAMESPACE).exists()
    (data / 'first-boot').touch()
    assert identity.main(['install-create', '--installer']) == 0
    before = record_path(data).read_bytes()
    assert identity.main(['install-create', '--installer']) == 1
    assert record_path(data).read_bytes() == before


def test_cli_install_refuses_a_live_middleware_socket(cli):
    data, _ = cli
    (data / 'first-boot').touch()
    identity.MIDDLEWARE_SOCKETS[0].touch()
    assert identity.main(['install-create', '--installer']) == 1
    assert not (data / identity.NAMESPACE).exists()


@pytest.mark.parametrize('command', ['status', 'recover', 'install-create'])
def test_cli_requires_local_root(cli, monkeypatch, command):
    data, _ = cli
    monkeypatch.setattr(os, 'geteuid', lambda: 12345)
    assert identity.main([command]) == 1
    assert not (data / identity.NAMESPACE).exists()


def test_cli_refuses_unbranded_target(cli):
    data, _ = cli
    (data / '.vendor').write_text('{"name":"Other"}')
    (data / 'first-boot').touch()
    assert identity.main(['install-create', '--installer']) == 1
    assert identity.main(['recover']) == 1
    assert not (data / identity.NAMESPACE).exists()


def test_cli_recovery_checks_twice_and_never_restarts_services(cli, monkeypatch, capsys):
    data, _ = cli
    calls = []
    reply = replies()
    def call(method, *args):
        calls.append(method)
        return reply(method, *args)
    monkeypatch.setattr(identity, 'middleware_call', call)
    def no_process(*_args, **_kwargs):
        raise AssertionError('Recovery must not stop services or reboot')
    monkeypatch.setattr(identity.subprocess, 'run', no_process)
    assert identity.main(['recover']) == 0
    assert calls == ['docker.config', 'app.query', 'api_key.query'] * 2
    before = record_path(data).read_bytes()
    calls.clear()
    assert identity.main(['recover']) == 0
    assert calls == []
    assert record_path(data).read_bytes() == before
    assert 'Restart this server using the TrueNAS power menu' in capsys.readouterr().out


def test_cli_recovery_failure_at_final_check_leaves_legacy(cli, monkeypatch):
    data, legacy = cli
    count = 0
    def check():
        nonlocal count
        count += 1
        if count == 2:
            raise identity.IdentityError('HexOS provisioning was detected')
    monkeypatch.setattr(identity, 'require_unprovisioned', check)
    assert identity.main(['recover']) == 1
    assert not (data / identity.NAMESPACE).exists()
    assert identity.selected_identity(data, legacy)[0] == 'legacy'


def test_cli_status_and_recover_never_repair_corrupt_identity(cli, monkeypatch):
    data, _ = cli
    path = put_record(data, b'broken')
    monkeypatch.setattr(identity, 'middleware_call', lambda *_args: pytest.fail('Unexpected middleware call'))
    assert identity.main(['status']) == 1
    assert identity.main(['recover']) == 1
    assert path.read_bytes() == b'broken'


@pytest.mark.parametrize('mode', [0o775, 0o777])
def test_legacy_parent_mode_does_not_change_existing_identity(target, mode):
    data, legacy = target
    data.chmod(mode)
    assert identity.selected_identity(data, legacy) == ('legacy', hashlib.sha256(legacy.read_bytes()).hexdigest())
    with pytest.raises(identity.IdentityError):
        identity.create_identity(data)
    assert list(data.iterdir()) == []


def test_strong_parent_mode_remains_strict(target):
    data, legacy = target
    identity.create_identity(data)
    before = record_path(data).read_bytes()
    data.chmod(0o777)
    with pytest.raises(identity.IdentityError):
        identity.selected_identity(data, legacy)
    assert record_path(data).read_bytes() == before



def test_process_crash_before_publish_leaves_only_ignored_complete_stage(target):
    data, legacy = target
    child = os.fork()
    if child == 0:
        identity.create_identity(data, before_publish=lambda: os._exit(23))
        os._exit(99)
    _, status = os.waitpid(child, 0)
    assert os.waitstatus_to_exitcode(status) == 23
    assert not (data / identity.NAMESPACE).exists()
    stages = list(data.glob('.hexos-identity-*'))
    assert len(stages) == 1
    assert (stages[0] / identity.RECORD).stat().st_mode & 0o777 == 0o600
    assert len(json.loads((stages[0] / identity.RECORD).read_bytes())['id']) == 64
    assert identity.selected_identity(data, legacy)[0] == 'legacy'
    identity.create_identity(data)
    assert identity.selected_identity(data, legacy)[0] == 'v1'
    assert stages[0].exists()



def test_new_empty_namespace_between_checks_is_not_replaced_by_installer(target):
    data, _ = target
    namespace = data / identity.NAMESPACE
    def competing_creator():
        namespace.mkdir(mode=0o700)
    with pytest.raises(identity.IdentityError):
        identity.create_identity(data, before_publish=competing_creator)
    assert namespace.is_dir()
    assert list(namespace.iterdir()) == []



def test_installer_flag_is_required_even_with_first_boot_marker(target, monkeypatch):
    data, legacy = target
    (data / '.vendor').write_text('{"name":"HexOS"}')
    (data / 'first-boot').touch()
    monkeypatch.setattr(identity, 'DATA', data)
    monkeypatch.setattr(identity, 'LEGACY_HOSTID', legacy)
    monkeypatch.setattr(identity, 'MIDDLEWARE_SOCKETS', ())
    monkeypatch.setattr(identity.os, 'geteuid', lambda: 0)
    assert identity.main(['install-create']) == 1
    assert not (data / identity.NAMESPACE).exists()


def test_deep_json_parser_failure_is_normalized(target, monkeypatch):
    import sys
    data, legacy = target
    put_record(data, b'[' * 1500 + b']' * 1500)
    # Python 3.12's C decoder has its own recursion budget. Exercise the real
    # Python decoder so this failure oracle is stable across native versions.
    monkeypatch.setattr(json.scanner, 'make_scanner', json.scanner.py_make_scanner)
    previous_limit = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(500)
        with pytest.raises(identity.IdentityError) as captured:
            identity.selected_identity(data, legacy)
        assert isinstance(captured.value.__cause__, RecursionError)
    finally:
        sys.setrecursionlimit(previous_limit)


def test_readable_nonregular_record_is_not_accepted_as_identity(target, monkeypatch):
    import stat
    from types import SimpleNamespace
    data, legacy = target
    path = put_record(data, valid_record())
    real_fstat = os.fstat
    inode = path.stat().st_ino
    def device_metadata(fd):
        info = real_fstat(fd)
        if info.st_ino == inode:
            return SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_uid=identity.OWNER_UID)
        return info
    monkeypatch.setattr(identity.os, 'fstat', device_metadata)
    with pytest.raises(identity.IdentityError, match='regular file'):
        identity.selected_identity(data, legacy)



@pytest.mark.parametrize('part', ['namespace', 'record'])
def test_child_wrong_owner_refuses_with_valid_parent(target, monkeypatch, part):
    data, legacy = target
    path = put_record(data, valid_record())
    inode = (path if part == 'record' else path.parent).stat().st_ino
    real_fstat = os.fstat
    def wrong_child_owner(fd):
        info = real_fstat(fd)
        if info.st_ino == inode:
            values = list(info)
            values[4] = identity.OWNER_UID + 1
            return os.stat_result(values)
        return info
    monkeypatch.setattr(identity.os, 'fstat', wrong_child_owner)
    with pytest.raises(identity.IdentityError, match='owned by root'):
        identity.selected_identity(data, legacy)

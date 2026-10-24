"""Exercise the vendor launcher with real identity and branding readers.

Only the service package initializer and process boundaries are isolated. The
initializer loads the entire middleware framework, which this launcher does not
need. No test starts systemd or opens a network connection.
"""

from configparser import ConfigParser
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import shlex
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from middlewared.scripts import hexos_identity as identity

VENDOR_SOURCE = Path(identity.__file__).with_name('vendor_service.py')


@pytest.fixture
def launcher(tmp_path, monkeypatch):
    package_name = 'middlewared.plugins.system_vendor'
    package = ModuleType(package_name)
    package.__path__ = [str(Path(identity.__file__).parents[1] / 'plugins' / 'system_vendor')]
    monkeypatch.setitem(sys.modules, package_name, package)
    spec = importlib.util.spec_from_file_location('hexos_vendor_identity_under_test', VENDOR_SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    data = tmp_path / 'data'
    data.mkdir(mode=0o700)
    legacy = tmp_path / 'hostid'
    legacy.write_bytes(b'\n\x01\x02 ')
    brand = data / '.vendor'
    brand.write_text(json.dumps({'name': 'HexOS'}))
    env = tmp_path / 'websocat'
    env.write_text('# Preserve existing service environment\nHEXOS_TEST=one=two\n\n')

    monkeypatch.setattr(identity, 'OWNER_UID', os.geteuid())
    monkeypatch.setattr(module, 'selected_identity', lambda: identity.selected_identity(data, legacy))
    monkeypatch.setitem(module.get_vendor.__globals__, 'SENTINEL_FILE_PATH', str(brand))
    load_envvars = module.load_envvars
    monkeypatch.setattr(module, 'load_envvars', lambda _path: load_envvars(str(env)))
    route = Mock(return_value='8.8.8.8 via 192.0.2.1 dev eth0 src 192.0.2.20 uid 0\n')
    run = Mock()
    monkeypatch.setattr(module, 'subprocess', SimpleNamespace(check_output=route, run=run))
    return SimpleNamespace(module=module, data=data, legacy=legacy, brand=brand, route=route, run=run)


def strong_record(launcher, payload=None):
    namespace = launcher.data / identity.NAMESPACE
    namespace.mkdir(mode=0o700)
    record = namespace / identity.RECORD
    record.write_bytes(payload if payload is not None else json.dumps({
        'version': 1, 'id': bytes(range(32)).hex(),
    }).encode())
    record.chmod(0o600)
    return record


def assert_launch(launcher, expected):
    launcher.route.assert_called_once_with('ip -o -4 route get 8.8.8.8', shell=True, text=True)
    launcher.run.assert_called_once()
    argv = launcher.run.call_args.args[0]
    assert launcher.run.call_args.kwargs == {}
    assert argv[:-1] == [
        'systemd-run', '--unit=websocat', '--description=websocat daemon for HexOS',
        '--property=Restart=always', '--property=RestartSec=10', '--uid=www-data',
        '--setenv=URL=wss://api.hexos.com', '--setenv=HEXOS_TEST=one=two', '/bin/bash', '-c',
    ]
    assert shlex.split(argv[-1]) == [
        '/usr/local/libexec/wsocat', '--buffer-size', '4194304', '--ping-interval', '30',
        '--ping-timeout', '60', '--exit-on-eof', '--text', 'ws://127.0.0.1:6000/websocket',
        f'wss://api.hexos.com/server/{expected}/192.0.2.20',
    ]


def test_legacy_launch_keeps_exact_raw_byte_hash_and_service_arguments(launcher, capsys):
    expected = hashlib.sha256(launcher.legacy.read_bytes()).hexdigest()
    assert expected != hashlib.sha256(launcher.legacy.read_bytes().strip()).hexdigest()
    launcher.module.main()
    assert_launch(launcher, expected)
    assert not (launcher.data / identity.NAMESPACE).exists()
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('legacy_state', ['present', 'changed', 'absent'])
def test_strong_launch_uses_decoded_identity_and_never_depends_on_zfs_hostid(launcher, capsys, legacy_state):
    record = strong_record(launcher)
    before = record.read_bytes(), record.stat().st_mtime_ns
    if legacy_state == 'changed':
        launcher.legacy.write_bytes(b'different legacy bytes')
    elif legacy_state == 'absent':
        launcher.legacy.unlink()
    launcher.module.main()
    assert_launch(launcher, hashlib.sha256(bytes(range(32))).hexdigest())
    assert (record.read_bytes(), record.stat().st_mtime_ns) == before
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('failure', ['malformed', 'empty-namespace', 'unsafe-mode', 'symlink', 'missing-legacy'])
def test_uncertain_identity_writes_stderr_and_never_queries_route_or_launches(launcher, capsys, failure):
    if failure == 'missing-legacy':
        launcher.legacy.unlink()
    elif failure == 'empty-namespace':
        (launcher.data / identity.NAMESPACE).mkdir(mode=0o700)
    else:
        record = strong_record(launcher, b'{broken' if failure == 'malformed' else None)
        if failure == 'unsafe-mode':
            record.chmod(0o644)
        elif failure == 'symlink':
            destination = launcher.data / 'outside.json'
            record.rename(destination)
            record.symlink_to(destination)
    launcher.module.main()
    launcher.route.assert_not_called()
    launcher.run.assert_not_called()
    output = capsys.readouterr()
    assert output.out == ''
    assert output.err.count('truenas-hexos-identity status') == 1
    assert 'HexOS identity:' in output.err
    assert 'Traceback (most recent call last):' in output.err
    assert 'selected_identity' in output.err
    assert any(name in output.err for name in ('IdentityError:', 'FileNotFoundError:', 'OSError:'))


def test_inherited_logging_configuration_cannot_swallow_identity_failure(launcher, monkeypatch, capsys):
    strong_record(launcher, b'{broken')
    # Middleware imports can install handlers before the vendor launcher runs.
    # With stdout discarded by systemd, neither handler routing nor logging
    # thresholds may hide the direct stderr diagnostic and traceback.
    for logger in (logging.getLogger(), logging.getLogger(launcher.module.__name__)):
        monkeypatch.setattr(logger, 'handlers', [logging.NullHandler()])
        monkeypatch.setattr(logger, 'propagate', False)
        monkeypatch.setattr(logger, 'disabled', True)
        monkeypatch.setattr(logger, 'level', logging.CRITICAL + 1)
    launcher.module.main()
    launcher.route.assert_not_called()
    launcher.run.assert_not_called()
    output = capsys.readouterr()
    assert output.out == ''
    assert 'truenas-hexos-identity status' in output.err
    assert 'Traceback (most recent call last):' in output.err
    assert 'IdentityError:' in output.err


def test_restart_selects_same_record_without_creating_or_repairing_identity(launcher):
    record = strong_record(launcher)
    before = record.read_bytes(), record.stat().st_mtime_ns
    launcher.module.main()
    first = launcher.run.call_args
    launcher.module.main()
    assert launcher.run.call_count == 2
    assert launcher.run.call_args == first
    assert (record.read_bytes(), record.stat().st_mtime_ns) == before


@pytest.mark.parametrize('name', ['TrueNAS Scale', '', None])
def test_non_hexos_brand_never_reads_identity_or_launches(launcher, monkeypatch, name):
    launcher.brand.write_text(json.dumps({'name': name}))
    selected = Mock(side_effect=AssertionError('Non-HexOS must not inspect HexOS identity'))
    monkeypatch.setattr(launcher.module, 'selected_identity', selected)
    launcher.module.main()
    selected.assert_not_called()
    launcher.route.assert_not_called()
    launcher.run.assert_not_called()


def test_packaged_vendor_service_keeps_errors_visible_when_stdout_is_discarded():
    service = Path(identity.__file__).parents[4] / 'debian' / 'debian' / 'ix-vendor.service'
    unit = ConfigParser(interpolation=None)
    assert unit.read(service) == [str(service)]
    assert unit['Service']['StandardOutput'] == 'null'
    assert unit['Service']['StandardError'] == 'journal'

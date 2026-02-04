from middlewared.test.integration.assets.nvmet import nvmet_host, nvmet_port, nvmet_subsys
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_method_calls
from middlewared.test.integration.utils.client import truenas_server

REDACTED_SECRET = '********'
MB = 1024 * 1024
MB_100 = 100 * MB
HOST1_NQN = 'nqn.2011-06.com.truenas:uuid-68bf9433-63ef-49f5-a921-4c0f8190fd94:host1'
HOST1_KEY = 'DHHC-1:01:rxc6XaoJgTSN7GID7gPQidMAskFym01wNHdw5B3RA33UFFIc:'
REDACTED_SECRET = '********'
SUBSYS_NAME = 'subsys1'
SUBSYS_NAME2 = 'subsys2'


def test_nvmet_global_audit():
    orig_config = call('nvmet.global.config')
    try:
        with expect_audit_method_calls([{
            'method': 'nvmet.global.update',
            'params': [
                {
                    'xport_referral': False,
                }
            ],
            'description': 'Update NVMe target global',
        }]):
            payload = {
                'xport_referral': False,
            }
            call('nvmet.global.update', payload)
    finally:
        orig_config.pop('id', None)
        call('nvmet.global.update', orig_config)


def test_nvmet_host_audit():
    _config = None
    try:
        # CREATE
        with expect_audit_method_calls([{
            'method': 'nvmet.host.create',
            'params': [
                {
                    'hostnqn': HOST1_NQN,
                }
            ],
            'description': f'Create NVMe target host {HOST1_NQN}',
        }]):
            payload = {
                'hostnqn': HOST1_NQN,
            }
            _config = call('nvmet.host.create', payload)
        # UPDATE
        with expect_audit_method_calls([{
            'method': 'nvmet.host.update',
            'params': [
                _config['id'],
                {
                    'dhchap_key': REDACTED_SECRET,
                }],
            'description': f'Update NVMe target host {HOST1_NQN}',
        }]):
            payload = {
                'dhchap_key': HOST1_KEY,
            }
            _config = call('nvmet.host.update', _config['id'], payload)
    finally:
        if _config is not None:
            # DELETE
            id_ = _config['id']
            with expect_audit_method_calls([{
                'method': 'nvmet.host.delete',
                'params': [id_],
                'description': f'Delete NVMe target host {HOST1_NQN}',
            }]):
                call('nvmet.host.delete', id_)


def test_nvmet_port_audit():
    _config = None
    try:
        # CREATE
        with expect_audit_method_calls([{
            'method': 'nvmet.port.create',
            'params': [
                {
                    'addr_trtype': 'TCP',
                    'addr_traddr': truenas_server.ip,
                    'addr_trsvcid': 4420,
                }
            ],
            'description': f'Create NVMe target port TCP:{truenas_server.ip}:4420',
        }]):
            payload = {
                'addr_trtype': 'TCP',
                'addr_traddr': truenas_server.ip,
                'addr_trsvcid': 4420,
            }
            _config = call('nvmet.port.create', payload)
        # UPDATE
        with expect_audit_method_calls([{
            'method': 'nvmet.port.update',
            'params': [
                _config['id'],
                {
                    'addr_trsvcid': 4444,
                }],
            'description': f'Update NVMe target port TCP:{truenas_server.ip}:4420',
        }]):
            payload = {
                'addr_trsvcid': 4444,
            }
            _config = call('nvmet.port.update', _config['id'], payload)
    finally:
        if _config is not None:
            # DELETE
            id_ = _config['id']
            with expect_audit_method_calls([{
                'method': 'nvmet.port.delete',
                'params': [id_],
                'description': f'Delete NVMe target port TCP:{truenas_server.ip}:4444',
            }]):
                call('nvmet.port.delete', id_)


def test_nvmet_subsys_audit():
    _config = None
    try:
        # CREATE
        with expect_audit_method_calls([{
            'method': 'nvmet.subsys.create',
            'params': [
                {
                    'name': SUBSYS_NAME,
                }
            ],
            'description': f'Create NVMe target subsys {SUBSYS_NAME}',
        }]):
            payload = {
                'name': SUBSYS_NAME,
            }
            _config = call('nvmet.subsys.create', payload)
        # UPDATE
        with expect_audit_method_calls([{
            'method': 'nvmet.subsys.update',
            'params': [
                _config['id'],
                {
                    'allow_any_host': True,
                }],
            'description': f'Update NVMe target subsys {SUBSYS_NAME}',
        }]):
            payload = {
                'allow_any_host': True,
            }
            _config = call('nvmet.subsys.update', _config['id'], payload)
    finally:
        if _config is not None:
            # DELETE
            id_ = _config['id']
            with expect_audit_method_calls([{
                'method': 'nvmet.subsys.delete',
                'params': [id_],
                'description': f'Delete NVMe target subsys {SUBSYS_NAME}',
            }]):
                call('nvmet.subsys.delete', id_)


def test_nvmet_host_subsys_audit():
    with nvmet_subsys(SUBSYS_NAME) as subsys1:
        with nvmet_subsys(SUBSYS_NAME2) as subsys2:
            with nvmet_host(HOST1_NQN) as host1:
                host_id = host1['id']
                subsys1_id = subsys1['id']
                subsys2_id = subsys2['id']
                _config = None
                try:
                    # CREATE
                    with expect_audit_method_calls([{
                        'method': 'nvmet.host_subsys.create',
                        'params': [
                            {
                                'subsys_id': subsys1_id,
                                'host_id': host_id,
                            }
                        ],
                        'description':
                        f'Create NVMe target host to subsystem mapping Host ID: {host_id} Subsys ID: {subsys1_id}',
                    }]):
                        payload = {
                            'subsys_id': subsys1_id,
                            'host_id': host_id,
                        }
                        _config = call('nvmet.host_subsys.create', payload)
                    # UPDATE
                    with expect_audit_method_calls([{
                        'method': 'nvmet.host_subsys.update',
                        'params': [
                            _config['id'],
                            {
                                'subsys_id': subsys2_id,
                            }],
                        'description': f'Update NVMe target host to subsystem mapping {HOST1_NQN}/{SUBSYS_NAME}',
                    }]):
                        payload = {
                            'subsys_id': subsys2_id,
                        }
                        _config = call('nvmet.host_subsys.update', _config['id'], payload)
                finally:
                    if _config is not None:
                        # DELETE
                        id_ = _config['id']
                        with expect_audit_method_calls([{
                            'method': 'nvmet.host_subsys.delete',
                            'params': [id_],
                            'description': f'Delete NVMe target host to subsystem mapping {HOST1_NQN}/{SUBSYS_NAME2}',
                        }]):
                            call('nvmet.host_subsys.delete', id_)


def test_nvmet_port_subsys_audit():
    with nvmet_subsys(SUBSYS_NAME) as subsys1:
        with nvmet_subsys(SUBSYS_NAME2) as subsys2:
            with nvmet_port(truenas_server.ip, 4420) as port1:
                port_id = port1['id']
                subsys1_id = subsys1['id']
                subsys2_id = subsys2['id']
                _config = None
                try:
                    # CREATE
                    with expect_audit_method_calls([{
                        'method': 'nvmet.port_subsys.create',
                        'params': [
                            {
                                'subsys_id': subsys1_id,
                                'port_id': port_id,
                            }
                        ],
                        'description':
                        f'Create NVMe target port to subsystem mapping Port ID: {port_id} Subsys ID: {subsys1_id}',
                    }]):
                        payload = {
                            'subsys_id': subsys1_id,
                            'port_id': port_id,
                        }
                        _config = call('nvmet.port_subsys.create', payload)
                    # UPDATE
                    with expect_audit_method_calls([{
                        'method': 'nvmet.port_subsys.update',
                        'params': [
                            _config['id'],
                            {
                                'subsys_id': subsys2_id,
                            }],
                        'description':
                        f'Update NVMe target port to subsystem mapping TCP:{truenas_server.ip}:4420/{SUBSYS_NAME}',
                    }]):
                        payload = {
                            'subsys_id': subsys2_id,
                        }
                        _config = call('nvmet.port_subsys.update', _config['id'], payload)
                finally:
                    if _config is not None:
                        # DELETE
                        id_ = _config['id']
                        with expect_audit_method_calls([{
                            'method': 'nvmet.port_subsys.delete',
                            'params': [id_],
                            'description':
                            f'Delete NVMe target port to subsystem mapping TCP:{truenas_server.ip}:4420/{SUBSYS_NAME2}',
                        }]):
                            call('nvmet.port_subsys.delete', id_)


def test_nvmet_namespace_audit():
    with dataset('nvmetnszvol', {
        'type': 'VOLUME',
        'volsize': MB_100
    }) as zvol_name:
        with nvmet_subsys(SUBSYS_NAME) as subsys:
            subsys_id = subsys['id']
            _config = None
            try:
                # CREATE
                with expect_audit_method_calls([{
                    'method': 'nvmet.namespace.create',
                    'params': [
                        {
                            'subsys_id': subsys_id,
                            'device_type': 'ZVOL',
                            'device_path': f'zvol/{zvol_name}'
                        }
                    ],
                    'description': f'Create NVMe target namespace Subsys ID: {subsys_id} device path: zvol/{zvol_name}',
                }]):
                    payload = {
                        'subsys_id': subsys_id,
                        'device_type': 'ZVOL',
                        'device_path': f'zvol/{zvol_name}'
                    }
                    _config = call('nvmet.namespace.create', payload)

                    assert _config['dataset'] is None
                    assert _config['relative_path'] is None

                # UPDATE
                with expect_audit_method_calls([{
                    'method': 'nvmet.namespace.update',
                    'params': [
                        _config['id'],
                        {
                            'nsid': 42,
                        }],
                    'description': f'Update NVMe target namespace {SUBSYS_NAME}/1',
                }]):
                    payload = {
                        'nsid': 42,
                    }
                    _config = call('nvmet.namespace.update', _config['id'], payload)
            finally:
                if _config is not None:
                    # DELETE
                    id_ = _config['id']
                    with expect_audit_method_calls([{
                        'method': 'nvmet.namespace.delete',
                        'params': [id_],
                        'description': f'Delete NVMe target namespace {SUBSYS_NAME}/42',
                    }]):
                        call('nvmet.namespace.delete', id_)

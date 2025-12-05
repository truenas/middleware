import os
import pytest
import libzfs

from middlewared.plugins.smb_.util_smbconf import (
    __parse_share_fs_acl,
    generate_smb_share_conf_dict,
    TrueNASVfsObjects
)
from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.io import set_io_uring_enabled
from middlewared.utils.smb import SMBSharePurpose

BASE_SMB_CONFIG = {
    'id': 1,
    'netbiosname': 'TESTSERVER',
    'netbiosalias': ['BOB', 'LARRY'],
    'workgroup': 'TESTDOMAIN',
    'description': 'TrueNAS Server',
    'unixcharset': 'UTF-8',
    'syslog': False,
    'aapl_extensions': False,
    'localmaster': False,
    'guest': 'nobody',
    'filemask': '',
    'dirmask': '',
    'smb_options': '',
    'bindip': [],
    'server_sid': 'S-1-5-21-732395397-2008429054-3061640861',
    'ntlmv1_auth': False,
    'enable_smb1': False,
    'admin_group': None,
    'next_rid': 0,
    'multichannel': False,
    'encryption': 'DEFAULT',
    'debug': False
}

BASE_SHARE = {
    'id': 1,
    'purpose': None,
    'path': '/mnt/dozer/BASE',
    'name': 'TEST_SHARE',
    'comment': 'canary',
    'access_based_share_enumeration': False,
    'browsable': True,
    'readonly': False,
    'audit': {
        'enable': False,
        'watch_list': [],
        'ignore_list': []
    },
    'enabled': True,
    'locked': False,
    'options': None,
}
LEGACY_SHARE_OPTS = {
    'path_suffix': '',
    'home': False,
    'guestok': False,
    'recyclebin': False,
    'hostsallow': [],
    'hostsdeny': [],
    'auxsmbconf': '',
    'aapl_name_mangling': False,
    'acl': True,
    'durablehandle': True,
    'streams': True,
    'timemachine': False,
    'timemachine_quota': 0,
    'vuid': '',
    'shadowcopy': True,
    'fsrvp': False,
    'afp': False,
}
DEFAULT_SHARE_OPTS = {'aapl_name_mangling': False}
MULTIPROTOCOL_SHARE_OPTS = {'aapl_name_mangling': False}
TIMEMACHINE_SHARE_OPTS = {
    'timemachine_quota': 0,
    'auto_snapshot': False,
    'auto_dataset_creation': False,
    'dataset_naming_schema': None,
    'vuid': 'd12aafdc-a7ac-4e3c-8bbd-6001f7f19819'
}
EXTERNAL_OPTS = {'remote_path': ['192.168.0.200\\SHARE']}

DEFAULT_SHARE = BASE_SHARE | {'purpose': SMBSharePurpose.DEFAULT_SHARE, 'options': DEFAULT_SHARE_OPTS}
LEGACY_SHARE = BASE_SHARE | {'purpose': SMBSharePurpose.LEGACY_SHARE, 'options': LEGACY_SHARE_OPTS}
EXTERNAL_SHARE = BASE_SHARE | {'path': 'EXTERNAL', 'purpose': SMBSharePurpose.EXTERNAL_SHARE, 'options': EXTERNAL_OPTS}


@pytest.fixture(scope='module')
def create_dataset():
    """
    Create a dataset under /root for testing path-realated functions
    Yields ZFS dataset handle
    """
    with libzfs.ZFS() as lz:
        root_zh = lz.get_dataset_by_path('/root')
        ds_name = os.path.join(root_zh.name, 'smb_share_test')
        root_zh.pool.create(ds_name, {})
        zhdl = lz.get_dataset(ds_name)
        zhdl.mount()
        try:
            yield zhdl
        finally:
            zhdl.umount()
            zhdl.delete()


@pytest.fixture(scope='function')
def posixacl_dataset(create_dataset):
    create_dataset.update_properties({'acltype': {'parsed': 'posix'}})
    vfs_objects = set()
    __parse_share_fs_acl(create_dataset.mountpoint, vfs_objects)
    assert not vfs_objects
    yield create_dataset.mountpoint


@pytest.fixture(scope='function')
def nfsacl_dataset(create_dataset):
    create_dataset.update_properties({'acltype': {'parsed': 'nfsv4'}})
    vfs_objects = set()
    __parse_share_fs_acl(create_dataset.mountpoint, vfs_objects)
    assert vfs_objects == {TrueNASVfsObjects.IXNAS}
    yield create_dataset.mountpoint


@pytest.fixture(scope='function')
def noacl_dataset(create_dataset):
    create_dataset.update_properties({'acltype': {'parsed': 'off'}})
    yield create_dataset.mountpoint


@pytest.fixture(scope='function')
def disable_io_uring():
    is_enabled = set_io_uring_enabled(False)
    assert is_enabled is False

    try:
        yield False
    finally:
        is_enabled = set_io_uring_enabled(True)

    assert is_enabled is True


def test__base_parameters(nfsacl_dataset):
    conf = generate_smb_share_conf_dict(None, DEFAULT_SHARE | {'path': nfsacl_dataset}, BASE_SMB_CONFIG)

    assert conf['smbd max xattr size'] == 2097152
    assert conf['comment'] == DEFAULT_SHARE['comment']
    assert conf['browseable'] == DEFAULT_SHARE['browsable']
    assert conf['ea support'] is False


def test__base_smb_nfs4acl(nfsacl_dataset):
    conf = generate_smb_share_conf_dict(None, DEFAULT_SHARE | {'path': nfsacl_dataset}, BASE_SMB_CONFIG)

    assert conf['path'] == nfsacl_dataset
    assert conf['vfs objects'] == [
        TrueNASVfsObjects.STREAMS_XATTR,
        TrueNASVfsObjects.SHADOW_COPY_ZFS,
        TrueNASVfsObjects.IXNAS,
        TrueNASVfsObjects.ZFS_CORE,
        TrueNASVfsObjects.IO_URING
    ]
    assert 'nt acl support' not in conf
    assert conf['available'] is True


def test__base_smb_posixacl(posixacl_dataset):
    conf = generate_smb_share_conf_dict(None, DEFAULT_SHARE | {'path': posixacl_dataset}, BASE_SMB_CONFIG)

    assert conf['path'] == posixacl_dataset
    assert conf['vfs objects'] == [
        TrueNASVfsObjects.STREAMS_XATTR,
        TrueNASVfsObjects.SHADOW_COPY_ZFS,
        TrueNASVfsObjects.ZFS_CORE,
        TrueNASVfsObjects.IO_URING
    ]
    assert 'nt acl support' not in conf
    assert conf['available'] is True


def test__base_smb_noacl(noacl_dataset):
    conf = generate_smb_share_conf_dict(None, DEFAULT_SHARE | {'path': noacl_dataset}, BASE_SMB_CONFIG)

    assert conf['path'] == noacl_dataset
    assert conf['vfs objects'] == [
        TrueNASVfsObjects.STREAMS_XATTR,
        TrueNASVfsObjects.SHADOW_COPY_ZFS,
        TrueNASVfsObjects.ZFS_CORE,
        TrueNASVfsObjects.IO_URING
    ]
    assert conf['nt acl support'] is False
    assert conf['available'] is True


def test__base_smb_locked(nfsacl_dataset):
    conf = generate_smb_share_conf_dict(None, DEFAULT_SHARE | {
        'path': nfsacl_dataset,
        'locked': True
    }, BASE_SMB_CONFIG)

    assert conf['path'] == nfsacl_dataset
    assert conf['available'] is False


def test__base_smb_disabled(nfsacl_dataset):
    conf = generate_smb_share_conf_dict(None, DEFAULT_SHARE | {
        'path': nfsacl_dataset,
        'enabled': False
    }, BASE_SMB_CONFIG)

    assert conf['path'] == nfsacl_dataset
    assert conf['available'] is False


def test__with_recyclebin_plain(nfsacl_dataset):
    smb = LEGACY_SHARE | {'path': nfsacl_dataset}
    smb['options']['recyclebin'] = True

    conf = generate_smb_share_conf_dict(None, smb, BASE_SMB_CONFIG)

    assert conf['vfs objects'] == [
        TrueNASVfsObjects.STREAMS_XATTR,
        TrueNASVfsObjects.SHADOW_COPY_ZFS,
        TrueNASVfsObjects.IXNAS,
        TrueNASVfsObjects.RECYCLE,
        TrueNASVfsObjects.ZFS_CORE,
        TrueNASVfsObjects.IO_URING
    ]
    assert conf['recycle:repository'] == '.recycle/%U'
    assert conf['recycle:keeptree'] is True
    assert conf['recycle:versions'] is True
    assert conf['recycle:touch'] is True
    assert conf['recycle:directory_mode'] == '0777'
    assert conf['recycle:subdir_mode'] == '0700'


@pytest.mark.parametrize('enabled', [True, False])
def test__with_recyclebin_ad(nfsacl_dataset, enabled):
    smb = LEGACY_SHARE | {'path': nfsacl_dataset}
    smb['options']['recyclebin'] = enabled
    conf = generate_smb_share_conf_dict(DSType.AD, smb, BASE_SMB_CONFIG)

    if enabled:
        assert conf['vfs objects'] == [
            TrueNASVfsObjects.STREAMS_XATTR,
            TrueNASVfsObjects.SHADOW_COPY_ZFS,
            TrueNASVfsObjects.IXNAS,
            TrueNASVfsObjects.RECYCLE,
            TrueNASVfsObjects.ZFS_CORE,
            TrueNASVfsObjects.IO_URING
        ]
        assert conf['recycle:repository'] == '.recycle/%D/%U'
        assert conf['recycle:keeptree'] is True
        assert conf['recycle:versions'] is True
        assert conf['recycle:touch'] is True
        assert conf['recycle:directory_mode'] == '0777'
        assert conf['recycle:subdir_mode'] == '0700'

    else:
        assert TrueNASVfsObjects.RECYCLE not in conf['vfs objects']
        assert not any([k.startswith('recycle') for k in conf.keys()])


@pytest.mark.parametrize('enabled', [True, False])
def test__durablehandle(nfsacl_dataset, enabled):
    conf = generate_smb_share_conf_dict(DSType.AD, DEFAULT_SHARE | {
        'path': nfsacl_dataset,
        'durablehandle': enabled,
    }, BASE_SMB_CONFIG)

    if enabled:
        assert conf['posix locking'] is False


@pytest.mark.parametrize('enabled', [True, False])
def test__readonly(nfsacl_dataset, enabled):
    conf = generate_smb_share_conf_dict(None, DEFAULT_SHARE | {
        'path': nfsacl_dataset,
        'readonly': enabled,
    }, BASE_SMB_CONFIG)

    assert conf['readonly'] is enabled


@pytest.mark.parametrize('enabled', [True, False])
def test__guestok(nfsacl_dataset, enabled):
    smb = LEGACY_SHARE | {'path': nfsacl_dataset}
    smb['options'] = LEGACY_SHARE_OPTS | {'guestok': enabled}
    conf = generate_smb_share_conf_dict(None, smb, BASE_SMB_CONFIG)

    assert conf['guest ok'] is enabled


@pytest.mark.parametrize('enabled', [True, False])
def test__acl_support(nfsacl_dataset, enabled):
    smb = LEGACY_SHARE | {'path': nfsacl_dataset}
    smb['options'] = LEGACY_SHARE_OPTS.copy() | {'acl': enabled}
    conf = generate_smb_share_conf_dict(None, smb, BASE_SMB_CONFIG)

    assert conf.get('nt acl support', True) is enabled


def test__fsrvp(nfsacl_dataset):
    smb = LEGACY_SHARE | {'path': nfsacl_dataset}
    smb['options'] = LEGACY_SHARE_OPTS.copy() | {'fsrvp': True}
    conf = generate_smb_share_conf_dict(None, smb, BASE_SMB_CONFIG)

    assert conf['path'] == nfsacl_dataset
    assert conf['vfs objects'] == [
        TrueNASVfsObjects.STREAMS_XATTR,
        TrueNASVfsObjects.SHADOW_COPY_ZFS,
        TrueNASVfsObjects.IXNAS,
        TrueNASVfsObjects.ZFS_CORE,
        TrueNASVfsObjects.IO_URING,
        TrueNASVfsObjects.ZFS_FSRVP,
    ]


@pytest.mark.parametrize('enabled', [True, False])
def test__access_based_share_enum(nfsacl_dataset, enabled):
    conf = generate_smb_share_conf_dict(None, DEFAULT_SHARE | {
        'path': nfsacl_dataset,
        'access_based_share_enumeration': enabled,
    }, BASE_SMB_CONFIG)
    assert conf['access based share enum'] is enabled


@pytest.mark.parametrize('fruit_enabled', [True, False])
def test__aapl_name_mangling(nfsacl_dataset, fruit_enabled):
    smb = DEFAULT_SHARE | {'path': nfsacl_dataset}
    smb['options'] = DEFAULT_SHARE_OPTS | {'aapl_name_mangling': True}
    conf = generate_smb_share_conf_dict(
        None, smb,
        BASE_SMB_CONFIG | {'aapl_extensions': fruit_enabled}
    )

    if fruit_enabled:
        assert TrueNASVfsObjects.FRUIT in conf['vfs objects']
        assert TrueNASVfsObjects.CATIA in conf['vfs objects']
        assert conf['fruit:encoding'] == 'native'
        assert conf['mangled names'] is False
        assert 'catia:mappings' not in conf
    else:
        assert TrueNASVfsObjects.FRUIT not in conf['vfs objects']
        assert TrueNASVfsObjects.CATIA in conf['vfs objects']
        assert conf['mangled names'] is False
        assert 'fruit:encoding' not in conf
        assert 'catia:mappings' in conf


def test__afp_share(nfsacl_dataset):
    smb = LEGACY_SHARE | {'path': nfsacl_dataset}
    smb['options'] = LEGACY_SHARE_OPTS | {'afp': True}
    conf = generate_smb_share_conf_dict(None, smb, BASE_SMB_CONFIG)

    assert conf['fruit:encoding'] == 'native'
    assert conf['fruit:metadata'] == 'netatalk'
    assert conf['fruit:resource'] == 'file'
    assert conf['streams_xattr:prefix'] == 'user.'
    assert conf['streams_xattr:store_stream_type'] is False
    assert conf['streams_xattr:xattr_compat'] is True


@pytest.mark.parametrize('tmopts', (
    {'auto_snapshot': True},
    {'auto_dataset_creation': True},
    {'auto_dataset_creation': True, 'dataset_naming_schema': '%M/%U'},
    {'timemachine_quota': 100},
))
def test__timemachine_preset(nfsacl_dataset, tmopts):
    conf = generate_smb_share_conf_dict(None, DEFAULT_SHARE | {
        'path': nfsacl_dataset,
        'purpose': 'TIMEMACHINE_SHARE',
        'options': TIMEMACHINE_SHARE_OPTS | tmopts
    }, BASE_SMB_CONFIG)

    if 'auto_snapshot' in tmopts:
        assert conf['vfs objects'][-1] == TrueNASVfsObjects.TMPROTECT

    if 'auto_dataset_creation' in tmopts:
        assert conf['zfs_core:zfs_auto_create'] is True
        suffix = tmopts.get('dataset_naming_schema', '%U')
        assert conf['path'] == f'{nfsacl_dataset}/{suffix}'

    if 'timemachine_quota' in tmopts:
        assert conf['fruit:time machine max size'] == tmopts['timemachine_quota']

    assert conf['fruit:time machine'] is True


@pytest.mark.parametrize('grace', [1000, 12000])
def test__worm_preset(nfsacl_dataset, grace):
    conf = generate_smb_share_conf_dict(None, DEFAULT_SHARE | {
        'path': nfsacl_dataset,
        'purpose': 'TIME_LOCKED_SHARE',
        'options': {'grace_period': grace}
    }, BASE_SMB_CONFIG)

    assert conf['path'] == nfsacl_dataset
    assert conf['vfs objects'] == [
        TrueNASVfsObjects.STREAMS_XATTR,
        TrueNASVfsObjects.SHADOW_COPY_ZFS,
        TrueNASVfsObjects.IXNAS,
        TrueNASVfsObjects.ZFS_CORE,
        TrueNASVfsObjects.IO_URING,
        TrueNASVfsObjects.WORM,
    ]
    assert conf['worm:grace_period'] == grace


def test__multiprotocol_nfs_preset(nfsacl_dataset):
    conf = generate_smb_share_conf_dict(None, DEFAULT_SHARE | {
        'path': nfsacl_dataset,
        'purpose': SMBSharePurpose.MULTIPROTOCOL_SHARE,
    }, BASE_SMB_CONFIG)

    assert conf['path'] == nfsacl_dataset
    assert conf['oplocks'] == 'no'


def test__shadow_copy_off(nfsacl_dataset):
    smb = LEGACY_SHARE | {'path': nfsacl_dataset}
    smb['options'] = LEGACY_SHARE_OPTS | {'shadowcopy': False}
    conf = generate_smb_share_conf_dict(None, smb, BASE_SMB_CONFIG)

    assert conf['vfs objects'] == [
        TrueNASVfsObjects.STREAMS_XATTR,
        TrueNASVfsObjects.IXNAS,
        TrueNASVfsObjects.ZFS_CORE,
        TrueNASVfsObjects.IO_URING,
    ]


def test__streams_off(nfsacl_dataset):
    smb = LEGACY_SHARE | {'path': nfsacl_dataset}
    smb['options'] = LEGACY_SHARE_OPTS | {'streams': False}
    conf = generate_smb_share_conf_dict(None, smb, BASE_SMB_CONFIG)

    assert conf['vfs objects'] == [
        TrueNASVfsObjects.SHADOW_COPY_ZFS,
        TrueNASVfsObjects.IXNAS,
        TrueNASVfsObjects.ZFS_CORE,
        TrueNASVfsObjects.IO_URING,
    ]


@pytest.mark.parametrize('enabled', [True, False])
def test__timemachine(nfsacl_dataset, enabled):
    smb = LEGACY_SHARE | {'path': nfsacl_dataset}
    smb['options']['timemachine'] = enabled
    conf = generate_smb_share_conf_dict(None, smb, BASE_SMB_CONFIG)

    if enabled:
        assert conf['fruit:time machine'] is True

    else:
        assert 'fruit:time machine' not in conf


@pytest.mark.parametrize('hostsconfig', [
    ('hostsallow', 'hosts allow'),
    ('hostsdeny', 'hosts deny')
])
def test__hosts(nfsacl_dataset, hostsconfig):
    db, smbconf = hostsconfig

    smb = LEGACY_SHARE | {'path': nfsacl_dataset}
    smb['options'][db] = ['jenny']
    conf = generate_smb_share_conf_dict(None, smb, BASE_SMB_CONFIG)

    assert conf[smbconf] == ['jenny']


@pytest.mark.parametrize('hostsconfig', [
    ('hostsallow', 'hosts allow'),
    ('hostsdeny', 'hosts deny')
])
def test__hosts_default_share(nfsacl_dataset, hostsconfig):
    db, smbconf = hostsconfig
    smb = DEFAULT_SHARE | {'path': nfsacl_dataset}
    smb['options'][db] = ['jenny']
    conf = generate_smb_share_conf_dict(None, smb, BASE_SMB_CONFIG)

    assert conf[smbconf] == ['jenny']


@pytest.mark.parametrize('path_suffix', ['%M/%U', None])
def test__homes_standalone(nfsacl_dataset, path_suffix):
    smb = LEGACY_SHARE | {'path': nfsacl_dataset}
    smb['options'] = LEGACY_SHARE_OPTS | {
        'path_suffix': path_suffix,
        'home': True
    }
    conf = generate_smb_share_conf_dict(None, smb, BASE_SMB_CONFIG)

    expected_suffix = path_suffix or '%U'
    assert conf['path'] == os.path.join(nfsacl_dataset, expected_suffix)


@pytest.mark.parametrize('path_suffix', ['%M/%U', None])
def test__homes_ad(nfsacl_dataset, path_suffix):
    smb = LEGACY_SHARE | {'path': nfsacl_dataset}
    smb['options'].update({
        'path_suffix': path_suffix,
        'home': True
    })
    conf = generate_smb_share_conf_dict(DSType.AD, smb, BASE_SMB_CONFIG)

    expected_suffix = path_suffix or '%D/%U'
    assert conf['path'] == os.path.join(nfsacl_dataset, expected_suffix)


@pytest.mark.parametrize('audit_config', [
    {'enable': True, 'watch_list': [], 'ignore_list': []},
    {'enable': True, 'watch_list': ['jenny'], 'ignore_list': []},
    {'enable': True, 'watch_list': [], 'ignore_list': ['jenny']},
])
def test__audit_config(nfsacl_dataset, audit_config):
    conf = generate_smb_share_conf_dict(DSType.AD, DEFAULT_SHARE | {
        'path': nfsacl_dataset,
        'audit': audit_config
    }, BASE_SMB_CONFIG | {'aapl_extensions': True})

    assert conf['vfs objects'] == [
        TrueNASVfsObjects.TRUENAS_AUDIT,
        TrueNASVfsObjects.FRUIT,
        TrueNASVfsObjects.STREAMS_XATTR,
        TrueNASVfsObjects.SHADOW_COPY_ZFS,
        TrueNASVfsObjects.IXNAS,
        TrueNASVfsObjects.ZFS_CORE,
        TrueNASVfsObjects.IO_URING,
    ]

    if audit_config['watch_list']:
        assert 'truenas_audit:watch_list' in conf, str(conf)
        assert conf['truenas_audit:watch_list'] == audit_config['watch_list']

    if audit_config['ignore_list']:
        assert 'truenas_audit:ignore_list' in conf, str(conf)
        assert conf['truenas_audit:ignore_list'] == audit_config['ignore_list']


def test__smb_external_share(nfsacl_dataset):
    conf = generate_smb_share_conf_dict(DSType.AD, EXTERNAL_SHARE, BASE_SMB_CONFIG)

    assert conf['path'] == '/var/empty'
    assert conf['msdfs root'] is True
    assert conf['msdfs proxy'] == EXTERNAL_OPTS['remote_path'][0]


def test__disabled_io_uring(nfsacl_dataset, disable_io_uring):
    conf = generate_smb_share_conf_dict(DSType.AD, DEFAULT_SHARE | {
        'path': nfsacl_dataset,
    }, BASE_SMB_CONFIG, disable_io_uring)

    assert TrueNASVfsObjects.IO_URING not in conf['vfs objects']


def test__aux_param_invalid(nfsacl_dataset):
    smb = LEGACY_SHARE | {'path': nfsacl_dataset}
    smb['options']['auxsmbconf'] = '\n'.join([
        'zfs_core:zfs_block_cloning = True',  # verify that enterprise feature removed
        'vfs objects = Canary', # verify that blacklist param removed
        '333',  # verify that invalid value removed
        '# test:one = canary',  # verify this type of comment is removed
        '; test:two = canary',  # verify that this comment is also removed
        'test:three = canary',  # This one should be added
    ])

    conf = generate_smb_share_conf_dict(None, smb, BASE_SMB_CONFIG)

    assert conf['vfs objects'] != 'canary'
    assert 'zfs_core:zfs_block_cloning' not in conf
    assert '333' not in conf
    assert '# test:one' not in conf
    assert '; test:two' not in conf
    assert 'test:three' in conf

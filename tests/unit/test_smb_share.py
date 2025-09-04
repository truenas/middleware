import os
import pytest
import libzfs

from middlewared.plugins.smb_.util_smbconf import (
    generate_smb_share_conf_dict,
    TrueNASVfsObjects
)
from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.io import set_io_uring_enabled

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

BASE_SMB_SHARE = {
    'id': 1,
    'purpose': 'NO_PRESET',
    'path': '/mnt/dozer/BASE',
    'path_suffix': '',
    'home': False,
    'name': 'TEST_SHARE',
    'comment': 'canary',
    'browsable': True,
    'ro': False,
    'guestok': False,
    'recyclebin': False,
    'hostsallow': [],
    'hostsdeny': [],
    'auxsmbconf': '',
    'aapl_name_mangling': False,
    'abe': False,
    'acl': True,
    'durablehandle': True,
    'streams': True,
    'timemachine': False,
    'timemachine_quota': 0,
    'vuid': '',
    'shadowcopy': True,
    'fsrvp': False,
    'enabled': True,
    'afp': False,
    'audit': {
        'enable': False,
        'watch_list': [],
        'ignore_list': []
    },
    'path_local': '/mnt/dozer/BASE',
    'locked': False
}


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
    yield create_dataset.mountpoint


@pytest.fixture(scope='function')
def nfsacl_dataset(create_dataset):
    create_dataset.update_properties({'acltype': {'parsed': 'nfsv4'}})
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
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {'path': nfsacl_dataset}, BASE_SMB_CONFIG)

    assert conf['smbd max xattr size'] == 2097152
    assert conf['comment'] == BASE_SMB_SHARE['comment']
    assert conf['browseable'] == BASE_SMB_SHARE['browsable']
    assert conf['ea support'] is False


def test__base_smb_nfs4acl(nfsacl_dataset):
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {'path': nfsacl_dataset}, BASE_SMB_CONFIG)

    assert conf['path'] == nfsacl_dataset
    assert conf['vfs objects'] == [
        TrueNASVfsObjects.STREAMS_XATTR,
        TrueNASVfsObjects.SHADOW_COPY_ZFS,
        TrueNASVfsObjects.IXNAS,
        TrueNASVfsObjects.ZFS_CORE,
        TrueNASVfsObjects.IO_URING
    ]
    assert conf['nt acl support'] is True
    assert conf['available'] is True


def test__base_smb_posixacl(posixacl_dataset):
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {'path': posixacl_dataset}, BASE_SMB_CONFIG)

    assert conf['path'] == posixacl_dataset
    assert conf['vfs objects'] == [
        TrueNASVfsObjects.STREAMS_XATTR,
        TrueNASVfsObjects.SHADOW_COPY_ZFS,
        TrueNASVfsObjects.ZFS_CORE,
        TrueNASVfsObjects.IO_URING
    ]
    assert conf['nt acl support'] is True
    assert conf['available'] is True


def test__base_smb_noacl(noacl_dataset):
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {'path': noacl_dataset}, BASE_SMB_CONFIG)

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
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'locked': True
    }, BASE_SMB_CONFIG)

    assert conf['path'] == nfsacl_dataset
    assert conf['available'] is False


def test__base_smb_disabled(nfsacl_dataset):
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'enabled': False
    }, BASE_SMB_CONFIG)

    assert conf['path'] == nfsacl_dataset
    assert conf['available'] is False


def test__with_recyclebin_plain(nfsacl_dataset):
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'recyclebin': True,
    }, BASE_SMB_CONFIG)

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
    conf = generate_smb_share_conf_dict(DSType.AD, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'recyclebin': enabled,
    }, BASE_SMB_CONFIG)

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
    conf = generate_smb_share_conf_dict(DSType.AD, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'durablehandle': enabled,
    }, BASE_SMB_CONFIG)

    if enabled:
        assert conf['posix locking'] is False


@pytest.mark.parametrize('enabled', [True, False])
def test__readonly(nfsacl_dataset, enabled):
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'ro': enabled,
    }, BASE_SMB_CONFIG)

    assert conf['readonly'] is enabled


@pytest.mark.parametrize('enabled', [True, False])
def test__guestok(nfsacl_dataset, enabled):
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'guestok': enabled,
    }, BASE_SMB_CONFIG)

    assert conf['guest ok'] is enabled


@pytest.mark.parametrize('enabled', [True, False])
def test__acl_support(nfsacl_dataset, enabled):
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'acl': enabled,
    }, BASE_SMB_CONFIG)

    assert conf['nt acl support'] is enabled


def test__fsrvp(nfsacl_dataset):
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'fsrvp': True,
    }, BASE_SMB_CONFIG)

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
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'abe': enabled,
    }, BASE_SMB_CONFIG)
    assert conf['access based share enum'] is enabled


@pytest.mark.parametrize('fruit_enabled', [True, False])
def test__aapl_name_mangling(nfsacl_dataset, fruit_enabled):
    conf = generate_smb_share_conf_dict(
        None, BASE_SMB_SHARE | {'path': nfsacl_dataset, 'aapl_name_mangling': True},
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
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'afp': True,
    }, BASE_SMB_CONFIG)

    assert conf['fruit:encoding'] == 'native'
    assert conf['fruit:metadata'] == 'netatalk'
    assert conf['fruit:resource'] == 'file'
    assert conf['streams_xattr:prefix'] == 'user.'
    assert conf['streams_xattr:store_stream_type'] is False
    assert conf['streams_xattr:xattr_compat'] is True


def test__tmprotect_preset(nfsacl_dataset):
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'purpose': 'ENHANCED_TIMEMACHINE',
    }, BASE_SMB_CONFIG)

    assert conf['path'] == f'{nfsacl_dataset}/%U'
    assert conf['vfs objects'] == [
        TrueNASVfsObjects.STREAMS_XATTR,
        TrueNASVfsObjects.SHADOW_COPY_ZFS,
        TrueNASVfsObjects.IXNAS,
        TrueNASVfsObjects.ZFS_CORE,
        TrueNASVfsObjects.IO_URING,
        TrueNASVfsObjects.TMPROTECT,
    ]

    assert conf['zfs_core:zfs_auto_create'] == 'true'
    assert conf['fruit:time machine'] is True


def test__worm_preset(nfsacl_dataset):
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'purpose': 'WORM_DROPBOX',
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


def test__multiprotocol_nfs_preset(nfsacl_dataset):
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'purpose': 'MULTI_PROTOCOL_NFS',
    }, BASE_SMB_CONFIG)

    assert conf['path'] == nfsacl_dataset
    assert conf['oplocks'] == 'no'


def test__shadow_copy_off(nfsacl_dataset):
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'shadowcopy': False,
    }, BASE_SMB_CONFIG)

    assert conf['vfs objects'] == [
        TrueNASVfsObjects.STREAMS_XATTR,
        TrueNASVfsObjects.IXNAS,
        TrueNASVfsObjects.ZFS_CORE,
        TrueNASVfsObjects.IO_URING,
    ]


def test__streams_off(nfsacl_dataset):
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'streams': False,
    }, BASE_SMB_CONFIG)

    assert conf['vfs objects'] == [
        TrueNASVfsObjects.SHADOW_COPY_ZFS,
        TrueNASVfsObjects.IXNAS,
        TrueNASVfsObjects.ZFS_CORE,
        TrueNASVfsObjects.IO_URING,
    ]


@pytest.mark.parametrize('enabled', [True, False])
def test__timemachine(nfsacl_dataset, enabled):
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'timemachine': enabled,
    }, BASE_SMB_CONFIG)

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

    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        db: ['jenny'],
    }, BASE_SMB_CONFIG)

    assert conf[smbconf] == ['jenny']


@pytest.mark.parametrize('path_suffix', ['%M/%U', None])
def test__homes_standalone(nfsacl_dataset, path_suffix):
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'path_suffix': path_suffix,
        'home': True
    }, BASE_SMB_CONFIG)

    expected_suffix = path_suffix or '%U'
    assert conf['path'] == os.path.join(nfsacl_dataset, expected_suffix)


@pytest.mark.parametrize('path_suffix', ['%M/%U', None])
def test__homes_ad(nfsacl_dataset, path_suffix):
    conf = generate_smb_share_conf_dict(DSType.AD, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'path_suffix': path_suffix,
        'home': True
    }, BASE_SMB_CONFIG)

    expected_suffix = path_suffix or '%D/%U'
    assert conf['path'] == os.path.join(nfsacl_dataset, expected_suffix)


def test__timemachine_preset(nfsacl_dataset):
    conf = generate_smb_share_conf_dict(None, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
        'purpose': 'TIMEMACHINE',
    }, BASE_SMB_CONFIG)

    assert conf['fruit:time machine'] is True


@pytest.mark.parametrize('audit_config', [
    {'enable': True, 'watch_list': [], 'ignore_list': []},
    {'enable': True, 'watch_list': ['jenny'], 'ignore_list': []},
    {'enable': True, 'watch_list': [], 'ignore_list': ['jenny']},
])
def test__audit_config(nfsacl_dataset, audit_config):
    conf = generate_smb_share_conf_dict(DSType.AD, BASE_SMB_SHARE | {
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
    conf = generate_smb_share_conf_dict(DSType.AD, BASE_SMB_SHARE | {
        'path': 'EXTERNAL:127.0.0.1\\SHARE',
    }, BASE_SMB_CONFIG | {'aapl_extensions': True})

    assert conf['path'] == '/var/empty'
    assert conf['msdfs root'] is True
    assert conf['msdfs proxy'] == '127.0.0.1\\SHARE'


def test__disabled_io_uring(nfsacl_dataset, disable_io_uring):
    conf = generate_smb_share_conf_dict(DSType.AD, BASE_SMB_SHARE | {
        'path': nfsacl_dataset,
    }, BASE_SMB_CONFIG, disable_io_uring)

    assert TrueNASVfsObjects.IO_URING not in conf['vfs objects']

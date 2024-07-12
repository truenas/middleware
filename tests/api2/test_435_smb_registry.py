import contextlib
import os
import pytest

from middlewared.service_exception import ValidationError
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call, ssh

DATASET_NAME = 'smb-reg'
SHARES = [f'REGISTRYTEST_{i}' for i in range(0, 5)]
PRESETS = [
    "DEFAULT_SHARE",
    "ENHANCED_TIMEMACHINE",
    "MULTI_PROTOCOL_NFS",
    "PRIVATE_DATASETS",
    "WORM_DROPBOX"
]
DETECTED_PRESETS = None

"""
Note: following sample auxiliary parameters and comments were
provided by a community member for testing. They do not represent
the opinion or recommendation of iXsystems.
"""
SAMPLE_AUX = [
    'follow symlinks = yes ',
    'veto files = /.windows/.mac/.zfs/',
    '# needed explicitly for each share to prevent default being set',
    'admin users = MY_ACCOUNT',
    '## NOTES:', '',
    "; aio-fork might cause smbd core dump/signal 6 in log in v11.1- see bug report [https://redmine.ixsystems.com/issues/27470]. Looks helpful but disabled until clear if it's responsible.", '', '',
    '### VFS OBJECTS (shadow_copy2 not included if no periodic snaps, so do it manually)', '',
    '# Include recycle, crossrename, and exclude readonly, as share=RW', '',
    '#vfs objects = zfs_space zfsacl winmsa streams_xattr recycle shadow_copy2 crossrename aio_pthread', '',
    'vfs objects = aio_pthread streams_xattr shadow_copy_zfs acl_xattr crossrename winmsa recycle', '',
    '# testing without shadow_copy2', '',
    'valid users = MY_ACCOUNT @ALLOWED_USERS',
    'invalid users = root anonymous guest',
    'hide dot files = yes',
]

SAMPLE_OPTIONS = [
    'mangled names = no',
    'dos charset = CP850',
    'unix charset = UTF-8',
    'strict sync = no',
    '',
    'min protocol = SMB2',
    'vfs objects = fruit streams_xattr  ',
    'fruit:model = MacSamba', 'fruit:posix_rename = yes ',
    'fruit:veto_appledouble = no',
    'fruit:wipe_intentionally_left_blank_rfork = yes ',
    'fruit:delete_empty_adfiles = yes ',
    '',
    'fruit:locking=none',
    'fruit:metadata=netatalk',
    'fruit:resource=file',
    'streams_xattr:prefix=user.',
    'streams_xattr:store_stream_type=no',
    'strict locking=auto',
    '# oplocks=no  # breaks Time Machine',
    ' level2 oplocks=no',
    '# spotlight=yes  # invalid without further config'
]


@contextlib.contextmanager
def create_smb_share(path, share_name, mkdir=False, options=None):
    cr_opts = options or {}

    if mkdir:
        call('filesystem.mkdir', path)

    with smb_share(path, share_name, cr_opts) as share:
        yield share


@contextlib.contextmanager
def setup_smb_shares(mountpoint):
    SHARE_DICT = {}

    for share in SHARES:
        share_path = os.path.join(mountpoint, share)
        call('filesystem.mkdir', share_path)
        new_share = call('sharing.smb.create', {
            'comment': 'My Test SMB Share',
            'name': share,
            'home': False,
            'path': share_path,
        })
        SHARE_DICT[share] = new_share['id']

    try:
        yield SHARE_DICT
    finally:
        for share_id in SHARE_DICT.values():
            call('sharing.smb.delete', share_id)


@pytest.fixture(scope='module')
def setup_for_tests():
    with dataset(DATASET_NAME, data={'share_type': 'SMB'}) as ds:
        smb_registry_mp = os.path.join('/mnt', ds)
        call('filesystem.setperm', {
            'path': smb_registry_mp,
            'mode': '777',
            'options': {'stripacl': True, 'recursive': True}
        }, job=True)

        with setup_smb_shares(smb_registry_mp) as shares:
            yield (smb_registry_mp, ds, shares)


@pytest.fixture(scope='module')
def share_presets():
    yield call('sharing.smb.presets')


def test__setup_for_tests(setup_for_tests):
    reg_shares = call('sharing.smb.reg_listshares')
    for share in SHARES:
        assert share in reg_shares


@pytest.mark.parametrize('smb_share', SHARES)
def test__rename_shares(setup_for_tests, smb_share):
    mp, ds, SHARE_DICT = setup_for_tests

    call('sharing.smb.update', SHARE_DICT[smb_share], {
        'name': f'NEW_{smb_share}'
    })


def test__renamed_shares_in_registry(setup_for_tests):
    """
    Share renames need to be explicitly tested because
    it will actually result in share being removed from
    registry and re-added with different name.
    """
    reg_shares = call('sharing.smb.reg_listshares')
    for share in SHARES:
        assert f'NEW_{share}' in reg_shares

    assert len(reg_shares) == len(SHARES)


def check_aux_param(param, share, expected, fruit_enable=False):
    val = call('smb.getparm', param, share)
    if param == 'vfs objects':
        expected_vfs_objects = expected.split()
        # We have to override someone's poor life choices and insert
        # vfs_fruit so that they don't have mysteriously broken time
        # machine shares
        if fruit_enable:
            expected_vfs_objects.append('fruit')

        assert set(expected_vfs_objects) == set(val)
    else:
        assert val == expected


@pytest.mark.parametrize('preset', PRESETS)
def test__test_presets(setup_for_tests, share_presets, preset):
    """
    This test iterates through SMB share presets,
    applies them to a single share, and then validates
    that the preset was applied correctly.

    In case of bool in API, simple check that appropriate
    value is set in return from sharing.smb.update will
    be sufficient. In case of auxiliary parameters, we
    need to be a bit more thorough. The preset will not
    be reflected in returned auxsmbconf and so we'll need
    to directly reach out and run smb.getparm.
    """
    mp, ds, SHARE_DICT = setup_for_tests
    if 'TIMEMACHINE' in preset:
        call('smb.update', {'aapl_extensions': True})

    to_test = share_presets[preset]['params']
    to_test_aux = to_test['auxsmbconf']
    new_conf = call('sharing.smb.update', SHARE_DICT['REGISTRYTEST_0'], {
        'purpose': preset
    })
    for entry in to_test_aux.splitlines():
        aux, val = entry.split('=', 1)
        check_aux_param(aux.strip(), new_conf['name'], val.strip())

    for k in to_test.keys():
        if k == "auxsmbconf":
            continue
        assert to_test[k] == new_conf[k]


def test__reset_smb(setup_for_tests):
    """
    Remove all parameters that might turn us into
    a MacOS-style SMB server (fruit).
    """
    mp, ds, SHARE_DICT = setup_for_tests
    call('sharing.smb.update', SHARE_DICT['REGISTRYTEST_0'], {
        "purpose": "NO_PRESET",
        "timemachine": False
    })
    call('smb.update', {'aapl_extensions': False})


def test__test_aux_param_on_update(setup_for_tests):
    SHARE_DICT = setup_for_tests[2]
    share_id = SHARE_DICT['REGISTRYTEST_0']
    share = call('sharing.smb.query', [['id', '=', share_id]], {'get': True})

    old_aux = share['auxsmbconf']
    results = call('sharing.smb.update', share_id, {
        'auxsmbconf': '\n'.join(SAMPLE_AUX)
    })
    new_aux = results['auxsmbconf']
    new_name = results['name']
    ncomments_sent = 0
    ncomments_recv = 0

    for entry in old_aux.splitlines():
        """
        Verify that aux params from last preset applied
        are still in effect. Parameters included in
        SAMPLE_AUX will never be in a preset so risk of
        collision is minimal.
        """
        aux, val = entry.split('=', 1)
        check_aux_param(aux.strip(), new_name, val.strip())

    for entry in new_aux.splitlines():
        """
        Verify that non-comment parameters were successfully
        applied to the running configuration.
        """
        if not entry:
            continue

        if entry.startswith(('#', ';')):
            ncomments_recv += 1
            continue

        aux, val = entry.split('=', 1)
        check_aux_param(aux.strip(), new_name, val.strip())

    """
    Verify comments aren't being stripped on update
    """
    for entry in SAMPLE_AUX:
        if entry.startswith(('#', ';')):
            ncomments_sent += 1

    assert ncomments_sent == ncomments_recv, new_aux


@contextlib.contextmanager
def setup_aapl_extensions(newvalue):
    oldvalue = call('smb.config')['aapl_extensions']
    try:
        if oldvalue != newvalue:
            call('smb.update', {'aapl_extensions': newvalue})
        yield
    finally:
        if oldvalue != newvalue:
            call('smb.update', {'aapl_extensions': oldvalue})


@pytest.fixture(scope='function')
def setup_tm_share(setup_for_tests):
    share_name = 'AUX_CREATE'
    path = os.path.join(setup_for_tests[0], share_name)
    with setup_aapl_extensions(True):
        with create_smb_share(path, share_name, True, {
            "home": False,
            "purpose": "ENHANCED_TIMEMACHINE",
            "auxsmbconf": '\n'.join(SAMPLE_AUX)
        }) as s:
            yield s


def test__test_aux_param_on_create(share_presets, setup_tm_share):
    share = setup_tm_share
    new_aux = share['auxsmbconf']
    pre_aux = share_presets["ENHANCED_TIMEMACHINE"]["params"]["auxsmbconf"]
    ncomments_sent = 0
    ncomments_recv = 0

    for entry in pre_aux.splitlines():
        """
        Verify that aux params from preset were applied
        successfully to the running configuration.
        """
        aux, val = entry.split('=', 1)
        check_aux_param(aux.strip(), share['name'], val.strip())

    for entry in new_aux.splitlines():
        """
        Verify that non-comment parameters were successfully
        applied to the running configuration.
        """
        if not entry:
            continue

        if entry.startswith(('#', ';')):
            ncomments_recv += 1
            continue

        aux, val = entry.split('=', 1)
        check_aux_param(aux.strip(), share['name'], val.strip(), True)

    """
    Verify comments aren't being stripped on update
    """
    for entry in SAMPLE_AUX:
        if entry.startswith(('#', ';')):
            ncomments_sent += 1

    assert ncomments_sent == ncomments_recv, f'new: {new_aux}, sample: {SAMPLE_AUX}'


def test__delete_shares(setup_for_tests):
    SHARE_DICT = setup_for_tests[2]
    for key in list(SHARE_DICT.keys()):
        call('sharing.smb.delete', SHARE_DICT[key])
        SHARE_DICT.pop(key)

    reg_shares = call('sharing.smb.reg_listshares')
    assert len(reg_shares) == 0, str(reg_shares)

    share_count = call('sharing.smb.query', [], {'count': True})
    assert share_count == 0


"""
Following battery of tests validate behavior of registry
with regard to homes shares
"""


def test__create_homes_share(setup_for_tests):
    mp, ds, share_dict = setup_for_tests
    home_path = os.path.join(mp, 'HOME_SHARE')
    call('filesystem.mkdir', home_path)

    new_share = call('sharing.smb.create', {
        "comment": "My Test SMB Share",
        "path": home_path,
        "home": True,
        "purpose": "NO_PRESET",
        "name": 'HOME_SHARE',
    })
    share_dict['HOME'] = new_share['id']

    reg_shares = call('sharing.smb.reg_listshares')
    assert any(['homes'.casefold() == s.casefold() for s in reg_shares]), str(reg_shares)


def test__toggle_homes_share(setup_for_tests):
    mp, ds, share_dict = setup_for_tests
    try:
        call('sharing.smb.update', share_dict['HOME'], {'home': False})
        reg_shares = call('sharing.smb.reg_listshares')
        assert not any(['homes'.casefold() == s.casefold() for s in reg_shares]), str(reg_shares)
    finally:
        call('sharing.smb.update', share_dict['HOME'], {'home': True})

    reg_shares = call('sharing.smb.reg_listshares')
    assert any(['homes'.casefold() == s.casefold() for s in reg_shares]), str(reg_shares)


def test__registry_rebuild_homes(setup_for_tests):
    """
    Abusive test.
    In this test we run behind middleware's back and
    delete a our homes share from the registry, and then
    attempt to rebuild by registry sync method. This
    method is called (among other places) when the CIFS
    service reloads.
    """
    ssh('net conf delshare HOMES')
    call('service.reload', 'cifs')
    reg_shares = call('sharing.smb.reg_listshares')
    assert any(['homes'.casefold() == s.casefold() for s in reg_shares]), str(reg_shares)


def test__test_smb_options():
    """
    Validate that user comments are preserved as-is
    """
    new_config = call('smb.update', {'smb_options': '\n'.join(SAMPLE_OPTIONS)})
    assert new_config['smb_options'].splitlines() == SAMPLE_OPTIONS


def test__test_invalid_share_aux_param_create(setup_for_tests):
    init_share_count = call('sharing.smb.query', [], {'count': True})
    with pytest.raises(ValidationError) as ve:
        call('sharing.smb.create', {'name': 'FAIL', 'path': setup_for_tests[0], 'auxsmbconf': 'oplocks = canary'})

    assert ve.value.attribute == 'sharingsmb_create.auxsmbconf'

    assert init_share_count == call('sharing.smb.query', [], {'count': True})


def test__test_invalid_share_aux_param_update(setup_for_tests):
    this_share = call('sharing.smb.create', {'name': 'FAIL', 'path': setup_for_tests[0]})

    try:
        with pytest.raises(ValidationError) as ve:
            call('sharing.smb.update', this_share['id'], {'auxsmbconf': 'oplocks = canary'})
    finally:
        call('sharing.smb.delete', this_share['id'])

    assert ve.value.attribute == 'sharingsmb_update.auxsmbconf'

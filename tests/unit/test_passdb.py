import os
import pytest
import secrets
import string
import subprocess

from dataclasses import asdict
from middlewared.plugins.smb_ import util_passdb
from middlewared.plugins.smb_.util_account_policy import (
    SMBAccountPolicy, sync_account_policy, get_account_policy
)
from middlewared.utils.crypto import generate_nt_hash
from time import sleep, time

PDB_DOMAIN = 'CANARY'
PDB_DOM_SID = 'S-1-5-21-710078819-430336432-4106732522'
PDB_DICT_DEFAULTS = {
    'username': None,
    'nt_username': '',
    'domain': PDB_DOMAIN,
    'full_name': None,
    'comment': '',
    'home_dir': '',
    'dir_drive': '',
    'logon_script': '',
    'profile_path': '',
    'user_rid': None,
    'group_rid': 513,  # samba default -- domain users rid
    'acct_desc': '',
    'acct_ctrl': util_passdb.UserAccountControl.NORMAL_ACCOUNT,
    'nt_pw': None,
    'logon_count': 0,
    'bad_pw_count': 0,
    'times': None
}

DEFAULT_ACCOUNT_POLICY = {
    "min_password_age": None,
    "max_password_age": None,
    "password_warn_period": None,
    "password_inactivity_period": None,
    "min_password_length": None,
    "password_history_length": None
}

SAMPLE_USER = {
    'id': 75,
    'uid': 3000,
    'username': 'pdbuser',
    'unixhash': '$6$rounds=656000$oYArtLuJhcfrwkkX$uUcNk1VdH7jHWZLd6HXT1svD3MXtS578sBx2oDrag3ZTxVFm41y1mIvpCHcR1/dcGiTiT/lhIyVD8m1QHgovq0',  # noqa
    'smbhash': '05BC65787F63B56CF6D47F16E32E3ABF',
    'home': '/var/empty',
    'shell': '/usr/sbin/nologin',
    'full_name': 'pdbuser_name',
    'builtin': False,
    'smb': True,
    'password_disabled': False,
    'ssh_password_enabled': False,
    'locked': False,
    'sudo_commands': [],
    'sudo_commands_nopasswd': [],
    'email': None,
    'group': {
        'id': 107,
        'bsdgrp_gid': 3000,
        'bsdgrp_group': 'pdbuser',
        'bsdgrp_builtin': False,
        'bsdgrp_sudo_commands': [],
        'bsdgrp_sudo_commands_nopasswd': [],
        'bsdgrp_smb': False
    },
    'groups': [
        90
    ],
    'sshpubkey': None,
    'immutable': False,
    'twofactor_auth_configured': False,
    'local': True,
    'sid': 'S-1-5-21-710078819-430336432-4106732522-20075',
    'roles': [],
    'last_password_change': 1711547527,  # Deliberately old password
}

PDB_DOMAIN = 'CANARY'
NORMAL_ACCOUNT = util_passdb.UserAccountControl.NORMAL_ACCOUNT
LOCKED_ACCOUNT = NORMAL_ACCOUNT | util_passdb.UserAccountControl.AUTO_LOCKED
DISABLED_ACCOUNT = NORMAL_ACCOUNT | util_passdb.UserAccountControl.DISABLED
EXPIRED_ACCOUNT = NORMAL_ACCOUNT | util_passdb.UserAccountControl.PASSWORD_EXPIRED
PDB_PASSWD_CHANGE_STR = 'Password last set:    Wed, 27 Mar 2024 06:52:07 PDT'


@pytest.fixture(scope='module')
def passdb_dir():
    os.makedirs(util_passdb.SMBPath.PASSDB_DIR.path, mode=0o700, exist_ok=True)
    os.makedirs(util_passdb.SMBPath.PRIVATEDIR.path, mode=0o700, exist_ok=True)

    # valid smb.conf is required for pdbedit command
    with open('/etc/smb4.conf', 'w') as f:
        f.write('[global]\n')
        f.flush()


@pytest.fixture(scope='function')
def pdb_times():
    yield util_passdb.PDBTimes(
        logon=0,
        logoff=util_passdb.PASSDB_TIME_T_MAX,
        kickoff=util_passdb.PASSDB_TIME_T_MAX,
        bad_password=0,
        pass_last_set=int(time()),
        pass_can_change=0,
        pass_must_change=util_passdb.PASSDB_TIME_T_MAX
    )


@pytest.fixture(scope='function')
def pdb_user(pdb_times):
    payload = PDB_DICT_DEFAULTS | {
        'username': SAMPLE_USER['username'],
        'full_name': SAMPLE_USER['full_name'],
        'user_rid': 20075,
        'times': pdb_times,
        'nt_pw': SAMPLE_USER['smbhash']
    }

    yield util_passdb.PDBEntry(**payload)


def check_pdbedit(usernames):
    """
    validate that standard Samba tools see same users. This can fail if for
    instance we fail to insert major / minor versions into passdb.tdb because
    samba will interpret it as containing struct samu version 0.
    """
    expected = set(usernames)
    found = []
    pdbedit = subprocess.run(['pdbedit', '-L'], capture_output=True)
    assert pdbedit.returncode == 0, pdbedit.stderr.decode()
    for entry in pdbedit.stdout.decode().strip().splitlines():
        found.append(entry.split(':')[0])

    assert len(found) == len(usernames), f'expected: {usernames}, found: {found}'

    found = set(found)
    missing = expected - found
    assert missing == set(), str(missing)

    extra = found - expected
    assert extra == set(), str(extra)


def check_password_set_timestamp():
    # This assumes that server TZ is PDT
    pdbedit = subprocess.run(['pdbedit', '-Lv'], capture_output=True)
    assert pdbedit.returncode == 0, pdbedit.stderr.decode()
    output = pdbedit.stdout.decode()
    assert PDB_PASSWD_CHANGE_STR in output, output


@pytest.mark.parametrize('pdbentrydict', [
    PDB_DICT_DEFAULTS | {'username': 'user1', 'full_name': 'user1', 'user_rid': 20071},
    PDB_DICT_DEFAULTS | {'username': 'user2', 'full_name': 'user2', 'user_rid': 20072, 'acct_ctrl': LOCKED_ACCOUNT},
    PDB_DICT_DEFAULTS | {'username': 'user3', 'full_name': 'user3', 'user_rid': 20073, 'acct_ctrl': DISABLED_ACCOUNT},
    PDB_DICT_DEFAULTS | {'username': 'user4', 'full_name': 'user4', 'user_rid': 20074, 'acct_ctrl': EXPIRED_ACCOUNT},
])
def test__insert_query_delete(pdbentrydict, passdb_dir, pdb_times):
    """ Add user, verify it shows in our query, verify that it shows in pdbedit, then delete it """

    # generate NT hash from randomized password
    nt_hash = generate_nt_hash(''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10)))
    payload = pdbentrydict | {'times': pdb_times, 'nt_pw': nt_hash}

    entry = util_passdb.PDBEntry(**payload)

    util_passdb.insert_passdb_entries([entry])

    try:
        contents = util_passdb.query_passdb_entries([], {})
        assert len(contents) == 1
        check_pdbedit([entry.username])
    finally:
        util_passdb.delete_passdb_entry(payload['username'], payload['user_rid'])

    assert asdict(entry) == contents[0]

    contents = util_passdb.query_passdb_entries([], {})
    assert len(contents) == 0, str(contents)


def test__smbhash_parser():
    """
    The `smbhash` field in samba has changed from being a smbpasswd string to simply
    containing the NT hash for user. This test ensures that we properly extract NT hash
    from both entry types.
    """
    smb_hash_legacy = "smbuser:3000:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX:05BC65787F63B56CF6D47F16E32E3ABF:[U         ]:LCT-66C7190E:"  # noqa
    nt_hash = "05BC65787F63B56CF6D47F16E32E3ABF"

    assert util_passdb.user_smbhash_to_nt_pw('smbuser', smb_hash_legacy) == nt_hash
    assert util_passdb.user_smbhash_to_nt_pw('smbuser', nt_hash) == nt_hash


@pytest.mark.parametrize('user_data,expected', [
    ({'locked': False, 'password_disabled': False}, util_passdb.UserAccountControl.NORMAL_ACCOUNT),
    ({'locked': True, 'password_disabled': False}, LOCKED_ACCOUNT),
    ({'locked': False, 'password_disabled': True}, DISABLED_ACCOUNT),
    ({'locked': True, 'password_disabled': True}, DISABLED_ACCOUNT | LOCKED_ACCOUNT),
])
def test__uac_flags_parser(user_data, expected):
    """
    This test validates mapping of account status parameters from our user table entries to
    MS-SAMU user account control flags
    """
    assert util_passdb.user_entry_to_uac_flags(user_data) == expected


@pytest.mark.parametrize('changes', [
    {'locked': True, 'full_name': 'bob'},
    {'smbhash': generate_nt_hash('Cats')},
])
def test__pdb_update(pdb_user, changes):
    """
    This test validates the helper function that generates updated PDBEntry based on user
    specified data. For example, if there is an existing entry we should preserve its
    timestamps.
    """
    sleep(1)
    now = int(time())
    user_entry = SAMPLE_USER | changes

    new_entry = util_passdb.user_entry_to_passdb_entry(PDB_DOMAIN, user_entry, asdict(pdb_user))

    # validate that timestamps were preserved
    assert now != new_entry.times.pass_last_set
    assert user_entry['last_password_change'] == new_entry.times.pass_last_set
    assert new_entry.nt_pw == user_entry['smbhash']
    assert new_entry.domain == PDB_DOMAIN
    assert util_passdb.user_entry_to_uac_flags(user_entry) == new_entry.acct_ctrl


def test__validate_pass_last_set():
    """
    This test checks that pdbedit shows the pass_last_set field appropriately
    If this is broken then account policy management over SMB protocol won't work
    """
    entry = util_passdb.user_entry_to_passdb_entry(PDB_DOMAIN, SAMPLE_USER)
    util_passdb.insert_passdb_entries([entry])

    try:
        check_password_set_timestamp()
    finally:
        util_passdb.delete_passdb_entry(entry.username, entry.user_rid)


@pytest.mark.parametrize('policy_item', SMBAccountPolicy)
def test__validate_account_policy(policy_item):
    full_policy = DEFAULT_ACCOUNT_POLICY.copy() | {policy_item.name.lower(): 10}
    sync_account_policy(full_policy)

    for to_check in SMBAccountPolicy:
        value = get_account_policy(to_check)
        if to_check == policy_item:
            if policy_item is SMBAccountPolicy.MIN_PASSWORD_LENGTH:
                assert value == 10
            else:
                assert value == 10 * 86400
        else:
            assert value == to_check.default


@pytest.mark.parametrize('nthash_str,error', [
    ('', 'SMB hash not available'),
    ('*', 'failed to parse SMB hash'),
    ('canary', 'failed to parse SMB hash'),
    ('B3F34FF0FBB772A1A70810CBB3320740B3F34FF0FBB772A1A70810CBB3320740', 'failed to parse SMB hash'),
    ('B3F34FF0FBB772A1A70810CBB3320740', None),
])
def test__invalid_smb_hash(nthash_str, error):
    user = SAMPLE_USER | {'smbhash': nthash_str}
    if error:
        with pytest.raises(ValueError, match=error):
            util_passdb.user_entry_to_passdb_entry(PDB_DOMAIN, user)
    else:
        util_passdb.user_entry_to_passdb_entry(PDB_DOMAIN, user)

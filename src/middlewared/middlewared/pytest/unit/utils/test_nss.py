import grp as py_grp
import pwd as py_pwd

import pytest
from middlewared.utils.nss import grp, pwd

BAD_UIDS = [987654, -1]
BAD_GIDS = [987654, -1]
BAD_NAMES = ["BogusName"]


def test__check_user_count():
    assert len(pwd.getpwall()['FILES']) == len(py_pwd.getpwall())


def test__check_group_count():
    assert len(grp.getgrall()['FILES']) == len(py_grp.getgrall())


def test__check_user_contents():
    py_users = py_pwd.getpwall()
    users = pwd.getpwall()['FILES']

    for py_entry, entry in zip(py_users, users):
        assert py_entry.pw_name == entry.pw_name
        assert py_entry.pw_uid == entry.pw_uid
        assert py_entry.pw_gid == entry.pw_gid
        assert py_entry.pw_gecos == entry.pw_gecos
        assert py_entry.pw_dir == entry.pw_dir
        assert py_entry.pw_shell == entry.pw_shell


def test__check_group_contents():
    py_groups = py_grp.getgrall()
    groups = grp.getgrall()['FILES']

    for py_entry, entry in zip(py_groups, groups):
        assert py_entry.gr_name == entry.gr_name
        assert py_entry.gr_gid == entry.gr_gid
        assert py_entry.gr_mem == entry.gr_mem


def test__check_user_dict_conversion():
    users_normal = pwd.getpwall()['FILES']
    users_dict = pwd.getpwall(as_dict=True)['FILES']

    for py_entry, entry in zip(users_normal, users_dict):
        assert py_entry.pw_name == entry['pw_name']
        assert py_entry.pw_uid == entry['pw_uid']
        assert py_entry.pw_gid == entry['pw_gid']
        assert py_entry.pw_gecos == entry['pw_gecos']
        assert py_entry.pw_dir == entry['pw_dir']
        assert py_entry.pw_shell == entry['pw_shell']


def test__check_group_dict_conversion():
    groups_normal = grp.getgrall()['FILES']
    groups_dict = grp.getgrall(as_dict=True)['FILES']

    for py_entry, entry in zip(groups_normal, groups_dict):
        assert py_entry.gr_name == entry['gr_name']
        assert py_entry.gr_gid == entry['gr_gid']
        assert py_entry.gr_mem == entry['gr_mem']


def test__check_user_misses():
    for uid in BAD_UIDS:
        with pytest.raises(KeyError) as ve:
            py_pwd.getpwuid(uid)
        assert 'uid not found' in str(ve)
        with pytest.raises(KeyError) as ve:
            pwd.getpwuid(uid)
        assert 'uid not found' in str(ve)
    for name in BAD_NAMES:
        with pytest.raises(KeyError) as ve:
            py_pwd.getpwnam(name)
        assert 'name not found' in str(ve)
        with pytest.raises(KeyError) as ve:
            pwd.getpwnam(name)
        assert 'name not found' in str(ve)


def test__check_group_misses():
    for uid in BAD_GIDS:
        with pytest.raises(KeyError) as ve:
            py_grp.getgrgid(uid)
        assert 'gid not found' in str(ve)
        with pytest.raises(KeyError) as ve:
            grp.getgrgid(uid)
        assert 'gid not found' in str(ve)
    for name in BAD_NAMES:
        with pytest.raises(KeyError) as ve:
            py_grp.getgrnam(name)
        assert 'name not found' in str(ve)
        with pytest.raises(KeyError) as ve:
            grp.getgrnam(name)
        assert 'name not found' in str(ve)


def test___iter_pwd():
    py_users = {u.pw_uid: u for u in py_pwd.getpwall()}

    for entry in pwd.iterpw():
        py_entry = py_users.pop(entry.pw_uid)

        assert py_entry.pw_name == entry.pw_name
        assert py_entry.pw_uid == entry.pw_uid
        assert py_entry.pw_gid == entry.pw_gid
        assert py_entry.pw_gecos == entry.pw_gecos
        assert py_entry.pw_dir == entry.pw_dir
        assert py_entry.pw_shell == entry.pw_shell

    assert py_users == {}, str(py_users)


def test___iter_grp():
    py_groups = {g.gr_name: g for g in py_grp.getgrall()}

    for entry in grp.itergrp():
        py_entry = py_groups.pop(entry.gr_name)

        assert py_entry.gr_name == entry.gr_name
        assert py_entry.gr_gid == entry.gr_gid
        assert py_entry.gr_mem == entry.gr_mem

    assert py_groups == {}, str(py_groups)

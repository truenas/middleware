import pwd as py_pwd
import grp as py_grp

from middlewared.utils.nss import grp, pwd


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
    py_groups = grp.getgrall()['FILES']
    groups = grp.getgrall(as_dict=True)['FILES']

    for py_entry, entry in zip(py_groups, groups):
        assert py_entry.gr_name == entry['gr_name']
        assert py_entry.gr_gid == entry['gr_gid']
        assert py_entry.gr_mem == entry['gr_mem']

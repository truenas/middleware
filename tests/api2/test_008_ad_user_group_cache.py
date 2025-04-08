#!/usr/bin/env python3

import errno
import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import SSH_TEST
from auto_config import password, user
from middlewared.service_exception import CallError
from middlewared.test.integration.assets.directory_service import active_directory
from middlewared.test.integration.utils import call


WINBIND_SEPARATOR = "\\"


@pytest.fixture(scope="module")
def do_ad_connection(request):
    with active_directory() as ad:
        # make sure we are extra sure cache fill complete
        cache_fill_job = call(
            'core.get_jobs',
            [['method', '=', 'directoryservices.cache.refresh_impl']],
            {'order_by': ['-id'], 'get': True}
        )
        if cache_fill_job['state'] == 'RUNNING':
            call('core.job_wait', cache_fill_job['id'], job=True)

        users = [x['username'] for x in call(
            'user.query', [['local', '=', False]],
        )]

        set_users = set(users)
        assert len(set_users) == len(users)

        groups = [x['name'] for x in call(
            'group.query', [['local', '=', False]],
        )]

        set_groups = set(groups)
        assert len(set_groups) == len(groups)

        yield ad | {'users': set_users, 'groups': set_groups}


def get_ad_user_and_group(ad_connection):
    WORKGROUP = ad_connection['dc_info']['Pre-Win2k Domain']

    domain_prefix = f'{WORKGROUP.upper()}{WINBIND_SEPARATOR}'
    ad_user = ad_connection['user_obj']['pw_name']
    ad_group = f'{domain_prefix}domain users'

    user = call(
        'user.query', [['username', '=', ad_user]],
        {'get': True}
    )

    group = call(
        'group.query', [['name', '=', ad_group]],
        {'get': True}
    )

    return (user, group)


def test_check_for_ad_users(do_ad_connection):
    """
    This test validates that wbinfo -u output matches entries
    we get through user.query
    """
    cmd = "wbinfo -u"
    results = SSH_TEST(cmd, user, password)
    assert results['result'], str(results['output'])
    wbinfo_entries = set(results['stdout'].splitlines())

    assert wbinfo_entries == do_ad_connection['users']


def test_check_for_ad_groups(do_ad_connection):
    """
    This test validates that wbinfo -g output matches entries
    we get through group.query
    """
    cmd = "wbinfo -g"
    results = SSH_TEST(cmd, user, password)
    assert results['result'], str(results['output'])
    wbinfo_entries = set(results['stdout'].splitlines())

    assert wbinfo_entries == do_ad_connection['groups']


def test_check_directoryservices_cache_refresh(do_ad_connection):
    """
    This test validates that middleware can successfully rebuild the
    directory services cache from scratch using the public API.

    This currently happens once per 24 hours. Result of failure here will
    be lack of users/groups visible in webui.
    """

    # Cache resides in tdb files. Remove the files to clear cache.
    cmd = 'rm -f /root/tdb/persistent/*'
    results = SSH_TEST(cmd, user, password)
    assert results['result'] is True, results['output']

    # directoryservices.cache_refresh job causes us to rebuild / refresh LDAP / AD users.
    call('directoryservices.cache.refresh_impl', job=True)

    users = set([x['username'] for x in call(
        'user.query', [['local', '=', False]]
    )])

    assert users == do_ad_connection['users']

    groups = set([x['name'] for x in call(
        'group.query', [['local', '=', False]],
    )])

    assert groups == do_ad_connection['groups']


def test_check_lazy_initialization_of_users_and_groups_by_name(do_ad_connection):
    """
    When users explicitly search for a directory service or other user
    by name or id we should hit pwd and grp modules and synthesize a
    result if the user / group is not in the cache. This special behavior
    only occurs when single filter of "name =" or "id =". So after the
    initial query that should result in insertion, we add a second filter
    to only hit the cache. Code paths are slightly different for lookups
    by id or by name and so they are tested separately.
    """

    cmd = 'rm -f /root/tdb/persistent/*'
    results = SSH_TEST(cmd, user, password)
    assert results['result'] is True, results['output']

    ad_user, ad_group = get_ad_user_and_group(do_ad_connection)

    assert ad_user['id_type_both'] is True
    assert ad_user['immutable'] is True
    assert ad_user['local'] is False
    assert ad_group['id_type_both'] is True
    assert ad_group['local'] is False

    cache_names = set([x['username'] for x in call(
        'user.query', [['local', '=', False]],
    )])

    assert cache_names == {ad_user['username']}

    cache_names = set([x['name'] for x in call(
        'group.query', [['local', '=', False]],
    )])

    assert cache_names == {ad_group['name']}


def test_check_lazy_initialization_of_users_and_groups_by_id(do_ad_connection):
    """
    When users explicitly search for a directory service or other user
    by name or id we should hit pwd and grp modules and synthesize a
    result if the user / group is not in the cache. This special behavior
    only occurs when single filter of "name =" or "id =". So after the
    initial query that should result in insertion, we add a second filter
    to only hit the cache. Code paths are slightly different for lookups
    by id or by name and so they are tested separately.
    """

    ad_user, ad_group = get_ad_user_and_group(do_ad_connection)

    cmd = 'rm -f /root/tdb/persistent/*'
    results = SSH_TEST(cmd, user, password)
    assert results['result'] is True, results['output']

    call('user.query', [['uid', '=', ad_user['uid']]], {'get': True})

    call('group.query', [['gid', '=', ad_group['gid']]], {'get': True})

    cache_names = set([x['username'] for x in call(
        'user.query', [['local', '=', False]],
    )])

    assert cache_names == {ad_user['username']}

    cache_names = set([x['name'] for x in call(
        'group.query', [['local', '=', False]],
    )])

    assert cache_names == {ad_group['name']}

@pytest.mark.parametrize('op_type', ('UPDATE', 'DELETE'))
def test_update_delete_failures(do_ad_connection, op_type):
    ad_user, ad_group = get_ad_user_and_group(do_ad_connection)

    for acct, prefix in ((ad_user, 'user'), (ad_group, 'group')):
        with pytest.raises(CallError) as ce:
            if op_type == 'UPDATE':
                call(f'{prefix}.update', acct['id'], {'smb': False})
            else:
                call(f'{prefix}.delete', acct['id'])

        assert ce.value.errno == errno.EPERM

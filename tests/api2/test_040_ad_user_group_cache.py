#!/usr/bin/env python3

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import SSH_TEST
from auto_config import password, user
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

        users = set([x['username'] for x in call(
            'user.query',
            [['local', '=', False]],
            {'extra': {'search_dscache': True}}
        )])

        groups = set([x['name'] for x in call(
            'group.query',
            [['local', '=', False]],
            {'extra': {'search_dscache': True}}
        )])

        yield ad | {'users': users, 'groups': groups}


def get_ad_user_and_group(ad_connection):
    WORKGROUP = ad_connection['dc_info']['Pre-Win2k Domain']

    domain_prefix = f'{WORKGROUP.upper()}{WINBIND_SEPARATOR}'
    ad_user = ad_connection['user_obj']['pw_name']
    ad_group = f'{domain_prefix}domain users'

    user = call(
        'user.query', [['username', '=', ad_user]],
        {'extra': {'search_dscache': True}, 'get': True}
    )

    group = call(
        'group.query', [['name', '=', ad_group]],
        {'extra': {'search_dscache': True}, 'get': True}
    )

    return (user, group)


def test_check_for_ad_users(do_ad_connection):
    """
    This test validates that we can query AD users using
    filter-option {"extra": {"search_dscache": True}}
    """
    cmd = "wbinfo -u"
    results = SSH_TEST(cmd, user, password)
    assert results['result'], str(results['output'])
    wbinfo_entries = set(results['stdout'].splitlines())

    assert wbinfo_entries == do_ad_connection['users']


def test_check_for_ad_groups(do_ad_connection):
    """
    This test validates that we can query AD groups using
    filter-option {"extra": {"search_dscache": True}}
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
        'user.query',
        [['local', '=', False]],
        {'extra': {'search_dscache': True}}
    )])

    assert users == do_ad_connection['users']

    groups = set([x['name'] for x in call(
        'group.query',
        [['local', '=', False]],
        {'extra': {'search_dscache': True}}
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

    cache_names = set([x['username'] for x in call(
        'user.query',
        [['local', '=', False]],
        {'extra': {'search_dscache': True}}
    )])

    assert cache_names == {ad_user['username']}

    cache_names = set([x['name'] for x in call(
        'group.query',
        [['local', '=', False]],
        {'extra': {'search_dscache': True}}
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

    call(
        'user.query', [['uid', '=', ad_user['uid']]],
        {'extra': {'search_dscache': True, 'get': True}}
    )

    call(
        'group.query', [['gid', '=', ad_group['gid']]],
        {'extra': {'search_dscache': True, 'get': True}}
    )

    cache_names = set([x['username'] for x in call(
        'user.query',
        [['local', '=', False]],
        {'extra': {'search_dscache': True}}
    )])

    assert cache_names == {ad_user['username']}

    cache_names = set([x['name'] for x in call(
        'group.query',
        [['local', '=', False]],
        {'extra': {'search_dscache': True}}
    )])

    assert cache_names == {ad_group['name']}

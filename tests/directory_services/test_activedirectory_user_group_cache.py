#!/usr/bin/env python3

import errno
import json
import pytest
from middlewared.service_exception import CallError
from middlewared.test.integration.assets.directory_service import directoryservice
from middlewared.test.integration.utils import call, ssh


WINBIND_SEPARATOR = "\\"


@pytest.fixture(scope="module")
def do_ad_connection(request):
    with directoryservice('ACTIVEDIRECTORY') as ad:
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


def get_ad_user_and_group(do_ad_connection):
    domain_info = do_ad_connection['domain_info']
    WORKGROUP = domain_info['domain_controller']['pre-win2k_domain']

    domain_prefix = f'{WORKGROUP.upper()}{WINBIND_SEPARATOR}'
    ad_user = do_ad_connection['account'].user_obj['pw_name']
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


def get_tdb_version_data(filename):
    tdb_data = ssh(f'tdbdump -k TRUENAS_VERSION {filename}')
    return json.loads(tdb_data.replace('\\22', '"'))


def check_cache_version():
    tn_version = call('system.version_short')
    tdb_v_usr = get_tdb_version_data('/var/db/system/directory_services/directoryservice_cache_user.tdb')
    assert tdb_v_usr['truenas_version'] == tn_version
    tdb_v_grp = get_tdb_version_data('/var/db/system/directory_services/directoryservice_cache_group.tdb')
    assert tdb_v_grp['truenas_version'] == tn_version


def test_check_for_ad_users(do_ad_connection):
    """
    This test validates that wbinfo -u output matches entries
    we get through user.query
    """
    check_cache_version()
    cmd = "wbinfo -u"
    results = ssh(cmd, complete_response=True)
    assert results['result'], str(results['output'])
    wbinfo_entries = set(results['stdout'].splitlines())

    assert wbinfo_entries == do_ad_connection['users']


def test_check_for_ad_groups(do_ad_connection):
    """
    This test validates that wbinfo -g output matches entries
    we get through group.query
    """
    cmd = "wbinfo -g"
    results = ssh(cmd, complete_response=True)
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
    ssh('rm -f /var/db/system/directory_services/*')

    # directoryservices.cache_refresh job causes us to rebuild / refresh LDAP / AD users.
    call('directoryservices.cache.refresh_impl', job=True)
    check_cache_version()

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

    ssh('rm -f /var/db/system/directory_services/*')
    ad_user, ad_group = get_ad_user_and_group(do_ad_connection)

    assert ad_user['immutable'] is True
    assert ad_user['local'] is False
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
    ssh('rm -f /var/db/system/directory_services/*')
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
        with pytest.raises(CallError, match='the identity provider') as ce:
            if op_type == 'UPDATE':
                call(f'{prefix}.update', acct['id'], {'smb': False})
            else:
                call(f'{prefix}.delete', acct['id'])

        assert ce.value.errno == errno.EPERM


def test_check_cache_expiration(do_ad_connection):
    # Make sure cache is up to date
    call('directoryservices.cache.refresh_impl', job=True)

    # Verify that we don't refresh when not expired
    assert call('directoryservices.cache.refresh_impl', job=True) is False

    # Forcibly expire the cache by setting the expiration timestamp to a past date
    cmd = 'python3 -c "from middlewared.plugins.directoryservices_.util_cache import expire_cache;'
    cmd += 'expire_cache()"'
    ssh(cmd)

    # Now verify that cache is rebuilt as expected
    assert call('directoryservices.cache.refresh_impl', job=True) is True

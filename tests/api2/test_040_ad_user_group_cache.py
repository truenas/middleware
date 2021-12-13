#!/usr/bin/env python3

# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, wait_on_job
from auto_config import hostname
from pytest_dependency import depends

try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME, ADNameServer
except ImportError:
    Reason = 'ADNameServer AD_DOMAIN, ADPASSWORD, or/and ADUSERNAME are missing in config.py"'
    pytestmark = pytest.mark.skip(reason=Reason)
else:
    from auto_config import dev_test
    # comment pytestmark for development testing with --dev-test
    pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

WINBIND_SEPARATOR = "\\"
nameserver1 = None
nameserver2 = None

job_id = None
job_status = None


# Create tests
@pytest.mark.dependency(name="GOT_DNS")
def test_01_get_nameserver1():
    global nameserver1
    results = GET("/network/configuration/")
    assert results.status_code == 200, results.text
    nameserver1 = results.json()['nameserver1']


@pytest.mark.dependency(name="SET_DNS")
def test_02_set_nameserver_for_ad(request):
    depends(request, ["GOT_DNS"])
    global payload
    payload = {
        "nameserver1": ADNameServer,
    }
    global results
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@pytest.mark.dependency(name="AD_ENABLED")
def test_03_enabling_activedirectory(request):
    depends(request, ["SET_DNS"])
    global payload, results, job_id
    payload = {
        "bindpw": ADPASSWORD,
        "bindname": ADUSERNAME,
        "domainname": AD_DOMAIN,
        "netbiosname": hostname,
        "dns_timeout": 15,
        "verbose_logging": True,
        "enable": True
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()['job_id']
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@pytest.mark.dependency(name="AD_IS_HEALTHY")
def test_05_get_activedirectory_state(request):
    """
    Issue no-effect operation on DC's netlogon share to
    verify that domain join is alive.

    Also get our current workgroup. During domain join, this
    will change to one appropriate for the AD environment. Used
    for AD names.
    """
    global WORKGROUP

    depends(request, ["AD_ENABLED"])
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text

    results = GET("/smb")
    assert results.status_code == 200, results.text
    WORKGROUP = results.json()['workgroup']


@pytest.mark.dependency(name="INITIAL_CACHE_FILL")
def test_06_wait_for_cache_fill(request):
    """
    Local user/group cache fill is a backgrounded task.
    Wait for it to successfully complete.
    """
    depends(request, ["AD_IS_HEALTHY"])
    results = GET('/core/get_jobs/?method=activedirectory.fill_cache')
    job_status = wait_on_job(results.json()[-1]['id'], 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@pytest.mark.dependency(name="AD_USERS_CACHED")
def test_07_check_for_ad_users(request):
    """
    This test validates that we can query AD users using
    filter-option {"extra": {"search_dscache": True}}
    """
    depends(request, ["INITIAL_CACHE_FILL"], scope="session")
    results = GET('/user', payload={
        'query-filters': [['local', '=', False]],
        'query-options': {'extra': {"search_dscache": True}},
    })
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text


@pytest.mark.dependency(name="AD_GROUPS_CACHED")
def test_08_check_for_ad_groups(request):
    """
    This test validates that we can query AD groups using
    filter-option {"extra": {"search_dscache": True}}
    """
    depends(request, ["INITIAL_CACHE_FILL"], scope="session")
    results = GET('/group', payload={
        'query-filters': [['local', '=', False]],
        'query-options': {'extra': {"search_dscache": True}},
    })
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text


@pytest.mark.dependency(name="REBUILD_AD_CACHE")
def test_09_check_directoryservices_cache_refresh(request):
    """
    This test validates that middleware can successfully rebuild the
    directory services cache from scratch using the public API.

    This currently happens once per 24 hours. Result of failure here will
    be lack of users/groups visible in webui.
    """
    depends(request, ["AD_USERS_CACHED", "AD_GROUPS_CACHED"], scope="session")

    """
    directoryservices.cache_refresh job causes us to rebuild / refresh
    LDAP / AD users.
    """
    results = GET('/directoryservices/cache_refresh/')
    assert results.status_code == 200, results.text
    refresh_job = results.json()
    job_status = wait_on_job(refresh_job, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    """
    Verify that the AD user / group cache was rebuilt successfully.
    """

    results = GET('/group', payload={
        'query-filters': [['local', '=', False]],
        'query-options': {'extra': {"search_dscache": True}},
    })
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text

    results = GET('/user', payload={
        'query-filters': [['local', '=', False]],
        'query-options': {'extra': {"search_dscache": True}},
    })
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text


@pytest.mark.dependency(name="LAZY_INITIALIZATION_BY_NAME")
def test_10_check_lazy_initialization_of_users_and_groups_by_name(request):
    """
    When users explicitly search for a directory service or other user
    by name or id we should hit pwd and grp modules and synthesize a
    result if the user / group is not in the cache. This special behavior
    only occurs when single filter of "name =" or "id =". So after the
    initial query that should result in insertion, we add a second filter
    to only hit the cache. Code paths are slightly different for lookups
    by id or by name and so they are tested separately.
    """
    depends(request, ["REBUILD_AD_CACHE"], scope="session")
    global ad_user_id
    global ad_domain_users_id
    domain_prefix = f'{WORKGROUP.upper()}{WINBIND_SEPARATOR}'
    ad_user = f'{domain_prefix}{ADUSERNAME.lower()}'
    ad_group = f'{domain_prefix}domain users'

    results = GET('/user', payload={
        'query-filters': [['username', '=', ad_user]],
        'query-options': {'extra': {"search_dscache": True}},
    })
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text

    ad_user_id = results.json()[0]['uid']
    assert results.json()[0]['username'] == ad_user, results.text 

    results = GET('/group', payload={
        'query-filters': [['group', '=', ad_group]],
        'query-options': {'extra': {"search_dscache": True}},
    })
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text

    ad_domain_users_id = results.json()[0]['gid']
    assert results.json()[0]['group'] == ad_group, results.text

    """
    The following two tests validate that cache insertion occurred.
    """
    results = GET('/user', payload={
        'query-filters': [['username', '=', ad_user], ['local', '=', False]],
        'query-options': {'extra': {"search_dscache": True}},
    })
    assert results.status_code == 200, results.text
    assert len(results.json()) == 1, results.text

    results = GET('/group', payload={
        'query-filters': [['group', '=', ad_group], ['local', '=', False]],
        'query-options': {'extra': {"search_dscache": True}},
    })
    assert results.status_code == 200, results.text
    assert len(results.json()) == 1, results.text


@pytest.mark.dependency(name="LAZY_INITIALIZATION_BY_ID")
def test_11_check_lazy_initialization_of_users_and_groups_by_id(request):
    """
    When users explicitly search for a directory service or other user
    by name or id we should hit pwd and grp modules and synthesize a
    result if the user / group is not in the cache. This special behavior
    only occurs when single filter of "name =" or "id =". So after the
    initial query that should result in insertion, we add a second filter
    to only hit the cache. Code paths are slightly different for lookups
    by id or by name and so they are tested separately.
    """
    depends(request, ["LAZY_INITIALIZATION_BY_NAME"], scope="session")

    results = GET('/user', payload={
        'query-filters': [['uid', '=', ad_user_id]],
        'query-options': {'extra': {"search_dscache": True}},
    })
    assert results.status_code == 200, results.text
    assert results.json()[0]['uid'] == ad_user_id, results.text 

    results = GET('/group', payload={
        'query-filters': [['gid', '=', ad_domain_users_id]],
        'query-options': {'extra': {"search_dscache": True}},
    })
    assert results.status_code == 200, results.text
    assert results.json()[0]['gid'] == ad_domain_users_id, results.text 

    """
    The following two tests validate that cache insertion occurred.
    """
    results = GET('/user', payload={
        'query-filters': [['uid', '=', ad_user_id], ['local', '=', False]],
        'query-options': {'extra': {"search_dscache": True}},
    })
    assert results.status_code == 200, results.text
    assert len(results.json()) == 1, results.text

    results = GET('/group', payload={
        'query-filters': [['gid', '=', ad_domain_users_id], ['local', '=', False]],
        'query-options': {'extra': {"search_dscache": True}},
    })
    assert results.status_code == 200, results.text
    assert len(results.json()) == 1, results.text


def test_39_leave_activedirectory(request):
    depends(request, ["AD_ENABLED"])
    global payload, results
    payload = {
        "username": ADUSERNAME,
        "password": ADPASSWORD
    }
    results = POST("/activedirectory/leave/", payload)
    assert results.status_code == 200, results.text


def test_41_remove_site(request):
    depends(request, ["AD_ENABLED"])
    payload = {"site": None, "use_default_domain": False}
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text


def test_42_reset_dns(request):
    depends(request, ["SET_DNS"])
    global payload
    payload = {
        "nameserver1": nameserver1,
    }
    global results
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text

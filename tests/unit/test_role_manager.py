import pytest

from middlewared.role import RoleManager, ROLES
from middlewared.utils import security
from truenas_api_client import Client


FAKE_METHODS = [
    ('fakemethod1', ['READONLY_ADMIN']),
    ('fakemethod2', ['FILESYSTEM_DATA_READ']),
    ('fakemethod3', ['CATALOG_WRITE']),
    ('fakemethod4', ['DOCKER_READ']),
    ('fakemethod5', ['ACCOUNT_READ']),
    ('fakemethod6', ['ACCOUNT_WRITE']),
]

FAKE_METHODS_NOSTIG = frozenset(['fakemethod3'])
ALL_METHODS = frozenset([method for method, roles in FAKE_METHODS])
WRITE_METHODS = frozenset(['fakemethod3', 'fakemethod6'])
READONLY_ADMIN_METHODS = ALL_METHODS - WRITE_METHODS
FULL_ADMIN_STIG = ALL_METHODS - FAKE_METHODS_NOSTIG
EXPECTED_FA_RESOURCES = frozenset({
    'failover.reboot.other_node',
    'truenas.accept_eula',
    'filesystem.put',
    'truenas.set_production',
    'system.shutdown',
    'config.reset',
    'system.reboot',
    'config.upload',
    'filesystem.get',
    'config.save',
    'core.ping_remote',
    'core.arp',
    'core.debug',
})


@pytest.fixture(scope='module')
def nostig_roles():
    # Generate list of expected roles that should be unavailable for STIG mode
    PREFIXES = (
        'VM', 'TRUECOMMAND', 'CATALOG', 'DOCKER', 'APPS', 'VIRT', 'TRUENAS_CONNECT', 'API_KEY', 'CONTAINER', 'LXC'
    )
    yield set([
        role_name for
        role_name in list(ROLES.keys()) if role_name.startswith(PREFIXES) and not role_name.endswith('READ')
    ])


@pytest.fixture(scope='module')
def role_manager():
    """ A role manager populated with made up methods """
    rm = RoleManager(roles=ROLES)
    for method, roles in FAKE_METHODS:
        rm.register_method(method_name=method, roles=roles)

    yield rm


@pytest.fixture(scope='function')
def tmp_role_manager():
    yield RoleManager(roles=ROLES)


@pytest.mark.parametrize('role_name', list(ROLES.keys()))
def test__roles_have_correct_stig_assignment(nostig_roles, role_name):
    role_to_check = ROLES[role_name]
    assert type(role_to_check.stig) in (security.STIGType, type(None))

    if role_to_check.stig is not None:
        assert role_name not in nostig_roles
    else:
        assert role_name in nostig_roles

    # There should only be one role that grants full admin privileges
    if role_name == 'FULL_ADMIN':
        assert role_to_check.full_admin is True
    else:
        assert role_to_check.full_admin is False


@pytest.mark.parametrize('role,method,enabled_stig_type,resources', [
    ('READONLY_ADMIN', 'CALL', None, READONLY_ADMIN_METHODS),
    ('READONLY_ADMIN', 'CALL', security.STIGType.GPOS, READONLY_ADMIN_METHODS),
    ('FULL_ADMIN', '*', None, {'*'}),
    ('FULL_ADMIN', 'CALL', security.STIGType.GPOS, FULL_ADMIN_STIG),
])
def test__roles_have_correct_allowlist(role_manager, role, method, enabled_stig_type, resources):
    allowlist = role_manager.allowlist_for_role(role, enabled_stig_type)
    allowlist_resources = set()
    for entry in allowlist:
        assert method == entry['method']
        allowlist_resources.add(entry['resource'])

    assert allowlist_resources == resources


def test__role_manager_reject_read_role_on_write_method(tmp_role_manager):
    with pytest.raises(ValueError, match='resource may not be granted to'):
        tmp_role_manager.register_method(method_name='canary.update', roles=['DOCKER_READ'])


def test__role_manager_reject_unknown_role(tmp_role_manager):
    with pytest.raises(ValueError, match='Invalid role'):
        tmp_role_manager.register_method(method_name='canary.update', roles=['DOESNOTEXIST_WRITE'])


def test__role_manager_reject_already_registered(tmp_role_manager):
    tmp_role_manager.register_method(method_name='canary.update', roles=['DOCKER_WRITE'])

    with pytest.raises(ValueError, match='is already registered in this role manager'):
        tmp_role_manager.register_method(method_name='canary.update', roles=['VM_WRITE'])


def test__check_readonly_role():
    """
    We _really_ shouldn't be directly assigning resources to FULL_ADMIN. The reason for this
    is that it provides no granularity for restricting what FA can do when STIG is enabled.
    Mostly we don't want methods like "docker.update" being populated here.
    """
    with Client() as c:
        method_allowlists = c.call('privilege.dump_role_manager')['method_allowlists']
        fa_resources = set([entry['resource'] for entry in method_allowlists['FULL_ADMIN']])
        assert fa_resources == EXPECTED_FA_RESOURCES

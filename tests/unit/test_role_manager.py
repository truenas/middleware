import pytest

from middlewared.role import RoleManager, ROLES
from middlewared.utils import security


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


@pytest.fixture(scope='module')
def nostig_roles():
    # Generate list of expected roles that should be unavailble for STIG mode
    PREFIXES = ('VM', 'TRUECOMMAND', 'CATALOG', 'DOCKER', 'APPS', 'VIRT')
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
def test__roles_have_corect_allowlist(role_manager, role, method, enabled_stig_type, resources):
    allowlist = role_manager.allowlist_for_role(role, enabled_stig_type)
    allowlist_resources = set()
    for entry in allowlist:
        assert method == entry['method']
        allowlist_resources.add(entry['resource'])

    assert allowlist_resources == resources

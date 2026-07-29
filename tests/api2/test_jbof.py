import errno

import pytest

from middlewared.test.integration.utils import call, mock
from middlewared.service_exception import ValidationError, ValidationErrors

FAKE_DATA = {
    'mgmt_ip1': '2.3.4.5',
    'mgmt_username': 'AdminUser',
    'mgmt_password': 'AdminPassword',
    'description': 'Pretend JBOF',
}


USED_RDMA = [
    {'rdma': 'mlx5_0', 'netdev': 'enp193s0f0np0'},
    {'rdma': 'mlx5_1', 'netdev': 'enp193s0f1np1'},
]


ENTITLED_DECLARATION = """
def mock(self, feature):
    from middlewared.utils.entitlements import Entitlement, Reason

    return Entitlement(entitled=True, reason=Reason.ENTITLED, column='HW+K', message='')
"""


def license_declaration(feature_names):
    """Declaration for a license listing one ES24N and carrying `feature_names`."""
    return f"""
def mock(self):
    from datetime import date

    from truenas_pylicensed import LicenseType

    from middlewared.utils.license import FeatureInfo, LicenseInfo

    return LicenseInfo(
        id='test-license',
        type=LicenseType.ENTERPRISE_SINGLE,
        model='F60',
        support_expires_at=date(2035, 1, 1),
        license_expires_at=None,
        features={{
            name: FeatureInfo(name=name, start_date=None, expires_at=None, source='enterprise')
            for name in {feature_names!r}
        }},
        serials=('TEST-000001',),
        enclosures={{'ES24N': 1}},
        contract_type='STANDARD',
    )
"""


@pytest.fixture(scope='module')
def one_licensed():
    """A license listing a single ES24N, with the JBOF entitlement granted.

    ``jbof.licensed`` reads the license and then consults the entitlement
    engine, so mocking ``jbof.licensed`` itself would mock over that gate.
    The entitlement needs mocking as well because a test VM's chassis does
    not detect as TrueNAS hardware and JBOF is not granted on the CE side.
    """
    with mock('truenas.license.info_private', declaration=license_declaration(['JBOF'])):
        with mock('truenas.entitlements.check', args=['JBOF'], declaration=ENTITLED_DECLARATION):
            yield


# The tests that need an unmocked or differently mocked license have to run
# before the first user of `one_licensed`: it is module scoped, so once it is
# set up its mock stays installed for the remainder of the module.
def test__jbof_create_no_license():
    with pytest.raises(ValidationErrors) as ve:
        call('jbof.create', FAKE_DATA)
    assert ve.value.errors == [
        ValidationError(
            'jbof_create.mgmt_ip1', 'This feature is not licensed', errno.EINVAL
        )
    ]


def test__jbof_licensed_without_feature_key():
    """A license listing shelves but carrying no JBOF key grants nothing.

    The entitlement is deliberately left unmocked so the denial comes from
    the real engine rather than from the test.
    """
    with mock('truenas.license.info_private', declaration=license_declaration([])):
        assert call('jbof.licensed') == 0


def test__jbof_licensed_counts_enclosures(one_licensed):
    assert call('jbof.licensed') == 1


def test__jbof_create_exceed_license(one_licensed):
    with mock('jbof.query', args=[[], {'count': True}], return_value=1):
        with pytest.raises(ValidationErrors) as ve:
            call('jbof.create', FAKE_DATA)
        assert ve.value.errors == [
            ValidationError(
                'jbof_create.mgmt_ip1',
                'Already configured the number of licensed emclosures: 1',
                errno.EINVAL,
            )
        ]


def test__jbof_create_no_rdma(one_licensed):
    with mock('rdma.get_link_choices', return_value=[]):
        with mock('rdma.get_link_choices', args=[True], return_value=[]):
            with pytest.raises(ValidationErrors) as ve:
                call('jbof.create', FAKE_DATA)
            assert ve.value.errors == [
                ValidationError(
                    'jbof_create.mgmt_ip1', 'No RDMA links are available', errno.EINVAL
                )
            ]


def test__jbof_create_used_rdma(one_licensed):
    with mock('rdma.get_link_choices', return_value=[]):
        with mock('rdma.get_link_choices', args=[True], return_value=USED_RDMA):
            with pytest.raises(ValidationErrors) as ve:
                call('jbof.create', FAKE_DATA)
            assert ve.value.errors == [
                ValidationError(
                    'jbof_create.mgmt_ip1',
                    'All RDMA links are configured',
                    errno.EINVAL,
                )
            ]

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


@pytest.fixture(scope='module')
def one_licensed():
    with mock('jbof.licensed', return_value=1):
        yield


def test__jbof_create_no_license():
    with pytest.raises(ValidationErrors) as ve:
        call('jbof.create', FAKE_DATA)
    assert ve.value.errors == [
        ValidationError(
            'jbof_create.mgmt_ip1', 'This feature is not licensed', errno.EINVAL
        )
    ]


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

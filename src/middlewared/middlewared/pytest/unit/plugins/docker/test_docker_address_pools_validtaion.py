import pytest

from middlewared.plugins.docker.validation_utils import validate_address_pools
from middlewared.service_exception import ValidationErrors


IP_IN_USE = [
  {
    'type': 'INET',
    'address': '172.20.0.33',
    'netmask': 16,
    'broadcast': '172.20.0.63'
  }
]


@pytest.mark.parametrize('user_specified_networks,error_msg', (
    (
        [],
        'At least one address pool must be specified'),
    (
        [{'base': '172.20.2.0/24', 'size': 27}],
        'Base network 172.20.2.0/24 overlaps with an existing system network'),
    (
        [{'base': '172.21.2.0/16', 'size': 10}],
        'Base network 172.21.2.0/16 cannot be smaller than the specified subnet size 10'),
    (
        [{'base': '172.21.2.0/16', 'size': 27}, {'base': '172.21.2.0/16', 'size': 27}],
        'Base network 172.21.2.0/16 is a duplicate of another specified network'
    ),
    (
        [{'base': '172.21.0.0/16', 'size': 27}, {'base': '172.22.0.0/16', 'size': 27}],
        ''
    ),
))
@pytest.mark.asyncio
async def test_address_pools_validation(user_specified_networks, error_msg):
    if error_msg:
        with pytest.raises(ValidationErrors) as ve:
            validate_address_pools(IP_IN_USE, user_specified_networks)

        assert ve.value.errors[0].errmsg == error_msg
    else:
        assert validate_address_pools(IP_IN_USE, user_specified_networks) is None

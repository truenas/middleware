import pytest
from unittest.mock import Mock

from middlewared.plugins.network import InterfaceService

OBJ = InterfaceService(Mock())


non_ha_with_1_v4ip = (
    {
        'aliases': [
            {
                'address': '1.1.1.1',
                'type': 'INET',
                'netmask': 24,
            },
        ]
    },
    (
        {
            'address': '1.1.1.1',
            'address_b': '',
            'netmask': 24,
            'vip': '',
            'version': 4,
        },
        []
    )
)

non_ha_with_1_v6ip = (
    {
        'aliases': [
            {
                'address': 'aaaa:bbbb:cccc:dddd::1',
                'type': 'INET6',
                'netmask': 64,
            },
        ]
    },
    (
        {
            'address': 'aaaa:bbbb:cccc:dddd::1',
            'address_b': '',
            'netmask': 64,
            'version': 6,
            'vip': '',
        },
        []
    )
)

non_ha_with_2_v4ips = (
    {
        'aliases': [
            {
                'address': '1.1.1.1',
                'type': 'INET',
                'netmask': 24,
            },
            {
                'address': '2.2.2.2',
                'type': 'INET',
                'netmask': 24,
            },
        ]
    },
    (
        {
            'address': '1.1.1.1',
            'address_b': '',
            'netmask': 24,
            'version': 4,
            'vip': '',
        },
        [{
            'address': '2.2.2.2',
            'address_b': '',
            'netmask': 24,
            'version': 4,
            'vip': '',
        }]
    )
)

non_ha_with_2_v6ips = (
    {
        'aliases': [
            {
                'address': 'aaaa:bbbb:cccc:dddd::1',
                'type': 'INET6',
                'netmask': 64,
            },
            {
                'address': 'aaaa:bbbb:cccc:eeee::1',
                'type': 'INET6',
                'netmask': 64,
            },
        ]
    },
    (
        {
            'address': 'aaaa:bbbb:cccc:dddd::1',
            'address_b': '',
            'netmask': 64,
            'version': 6,
            'vip': '',
        },
        [{
            'address': 'aaaa:bbbb:cccc:eeee::1',
            'address_b': '',
            'netmask': 64,
            'version': 6,
            'vip': '',
        }]
    )
)

non_ha_with_2_mixed_ips = (
    {
        'aliases': [
            {
                'address': '1.1.1.1',
                'type': 'INET',
                'netmask': 24,
            },
            {
                'address': 'aaaa:bbbb:cccc:dddd::1',
                'type': 'INET6',
                'netmask': 64,
            },
        ]
    },
    (
        {
            'address': '1.1.1.1',
            'address_b': '',
            'netmask': 24,
            'version': 4,
            'vip': '',
        },
        [{
            'address': 'aaaa:bbbb:cccc:dddd::1',
            'address_b': '',
            'netmask': 64,
            'version': 6,
            'vip': '',
        }]
    )
)

ha_with_1_v4ip = (
    {
        'aliases': [{
            'address': '1.1.1.1',
            'type': 'INET',
            'netmask': 24,
        }],
        'failover_aliases': [{
            'address': '1.1.1.2',
            'type': 'INET',
        }],
        'failover_virtual_aliases': [{
            'address': '1.1.1.3',
            'type': 'INET',
        }],
    },
    (
        {
            'address': '1.1.1.1',
            'address_b': '1.1.1.2',
            'netmask': 24,
            'version': 4,
            'vip': '1.1.1.3',
        },
        []
    )
)

ha_with_1_v6ip = (
    {
        'aliases': [{
            'address': 'aaaa:bbbb:cccc:dddd::1',
            'type': 'INET6',
            'netmask': 64,
        }],
        'failover_aliases': [{
            'address': 'aaaa:bbbb:cccc:dddd::2',
            'type': 'INET6',
        }],
        'failover_virtual_aliases': [{
            'address': 'aaaa:bbbb:cccc:dddd::3',
            'type': 'INET6',
        }],
    },
    (
        {
            'address': 'aaaa:bbbb:cccc:dddd::1',
            'address_b': 'aaaa:bbbb:cccc:dddd::2',
            'netmask': 64,
            'version': 6,
            'vip': 'aaaa:bbbb:cccc:dddd::3',
        },
        []
    )
)

ha_with_2_v4ips = (
    {
        'aliases': [
            {
                'address': '1.1.1.1',
                'type': 'INET',
                'netmask': 24,
            },
            {
                'address': '2.2.2.1',
                'type': 'INET',
                'netmask': 24,
            },
        ],
        'failover_aliases': [
            {
                'address': '1.1.1.2',
                'type': 'INET',
            },
            {
                'address': '2.2.2.2',
                'type': 'INET',
            },
        ],
        'failover_virtual_aliases': [
            {
                'address': '1.1.1.3',
                'type': 'INET',
            },
            {
                'address': '2.2.2.3',
                'type': 'INET'
            },
        ],
    },
    (
        {
            'address': '1.1.1.1',
            'address_b': '1.1.1.2',
            'netmask': 24,
            'version': 4,
            'vip': '1.1.1.3',
        },
        [{
            'address': '2.2.2.1',
            'address_b': '2.2.2.2',
            'netmask': 24,
            'version': 4,
            'vip': '2.2.2.3'
        }]
    )
)


ha_with_2_v6ips = (
    {
        'aliases': [
            {
                'address': 'aaaa:bbbb:cccc:dddd::1',
                'type': 'INET6',
                'netmask': 64,
            },
            {
                'address': 'aaaa:bbbb:3333:eeee::1',
                'type': 'INET6',
                'netmask': 64,
            },
        ],
        'failover_aliases': [
            {
                'address': 'aaaa:bbbb:cccc:dddd::2',
                'type': 'INET6',
            },
            {
                'address': 'aaaa:bbbb:3333:eeee::2',
                'type': 'INET6',
            },
        ],
        'failover_virtual_aliases': [
            {
                'address': 'aaaa:bbbb:cccc:dddd::3',
                'type': 'INET6',
            },
            {
                'address': 'aaaa:bbbb:3333:eeee::3',
                'type': 'INET6',
            },
        ],
    },
    (
        {
            'address': 'aaaa:bbbb:cccc:dddd::1',
            'address_b': 'aaaa:bbbb:cccc:dddd::2',
            'netmask': 64,
            'version': 6,
            'vip': 'aaaa:bbbb:cccc:dddd::3',
        },
        [{
            'address': 'aaaa:bbbb:3333:eeee::1',
            'address_b': 'aaaa:bbbb:3333:eeee::2',
            'netmask': 64,
            'version': 6,
            'vip': 'aaaa:bbbb:3333:eeee::3'
        }]
    )
)

ha_with_2_mixed_ips = (
    {
        'aliases': [
            {
                'address': 'aaaa:bbbb:cccc:dddd::1',
                'type': 'INET6',
                'netmask': 64,
            },
            {
                'address': '1.1.1.1',
                'type': 'INET',
                'netmask': 24,
            },
        ],
        'failover_aliases': [
            {
                'address': 'aaaa:bbbb:cccc:dddd::2',
                'type': 'INET6',
            },
            {
                'address': '1.1.1.2',
                'type': 'INET',
            },
        ],
        'failover_virtual_aliases': [
            {
                'address': 'aaaa:bbbb:cccc:dddd::3',
                'type': 'INET6',
            },
            {
                'address': '1.1.1.3',
                'type': 'INET',
            },
        ],
    },
    (
        {
            'address': 'aaaa:bbbb:cccc:dddd::1',
            'address_b': 'aaaa:bbbb:cccc:dddd::2',
            'netmask': 64,
            'version': 6,
            'vip': 'aaaa:bbbb:cccc:dddd::3',
        },
        [{
            'address': '1.1.1.1',
            'address_b': '1.1.1.2',
            'netmask': 24,
            'version': 4,
            'vip': '1.1.1.3'
        }]
    )
)


@pytest.mark.parametrize('data, result', [
    non_ha_with_1_v4ip,
    non_ha_with_1_v6ip,
    non_ha_with_2_v4ips,
    non_ha_with_2_v6ips,
    non_ha_with_2_mixed_ips,
    ha_with_1_v4ip,
    ha_with_1_v6ip,
    ha_with_2_v4ips,
    ha_with_2_v6ips,
    ha_with_2_mixed_ips
])
def test_convert_aliases_to_datastore(data, result):
    iface, aliases = OBJ.convert_aliases_to_datastore(data)
    assert iface == result[0]
    assert aliases == result[1]

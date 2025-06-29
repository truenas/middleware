from unittest.mock import Mock, patch
import pytest

from middlewared.plugins.network import InterfaceService
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware


class MockInterface:
    """Mock interface object that mimics netif.Interface behavior."""
    def __init__(self, name, aliases):
        self.orig_name = name
        self._aliases = aliases

    def asdict(self):
        return {'aliases': self._aliases}


@pytest.fixture
def mock_interfaces():
    """Create a set of mock interfaces with various IPs."""
    return {
        'en0': MockInterface('en0', [
            {'type': 'INET', 'address': '192.168.1.10', 'netmask': 24, 'broadcast': '192.168.1.255'},
            {'type': 'INET6', 'address': '2001:db8::1', 'netmask': 64},
            {'type': 'INET6', 'address': 'fe80::1', 'netmask': 64},  # link-local
        ]),
        'en1': MockInterface('en1', [
            {'type': 'INET', 'address': '10.0.0.10', 'netmask': 24, 'broadcast': '10.0.0.255'},
            {'type': 'INET6', 'address': '2001:db8::2', 'netmask': 64},
        ]),
        'lo0': MockInterface('lo0', [
            {'type': 'INET', 'address': '127.0.0.1', 'netmask': 8, 'broadcast': '127.255.255.255'},
            {'type': 'INET6', 'address': '::1', 'netmask': 128},
        ]),
        'tap0': MockInterface('tap0', [  # Should be ignored by default
            {'type': 'INET', 'address': '172.16.0.1', 'netmask': 24, 'broadcast': '172.16.0.255'},
        ]),
    }


@pytest.fixture
def middleware_with_interfaces(mock_interfaces):
    """Create middleware with mocked interface methods."""
    m = Middleware()

    # Mock interface.query for static IP lookup
    m['interface.query'] = Mock(return_value=[
        {
            'aliases': [
                {'address': '192.168.1.10'},
                {'address': '2001:db8::1'},
            ],
            'failover_virtual_aliases': [],
            'name': 'en0',
        },
        {
            'aliases': [
                {'address': '10.0.0.10'},
            ],
            'failover_virtual_aliases': [],
            'name': 'en1',
        }
    ])

    # Mock failover.licensed
    m['failover.licensed'] = Mock(return_value=False)

    # Mock interface.internal_interfaces
    m['interface.internal_interfaces'] = Mock(return_value=['tap', 'epair'])

    return m


def test_ip_in_use_default_behavior(middleware_with_interfaces, mock_interfaces):
    """Test default behavior returns all IPs from all non-internal interfaces."""
    with patch('middlewared.plugins.network.netif') as mock_netif:
        mock_netif.list_interfaces = Mock(return_value=mock_interfaces)

        service = create_service(middleware_with_interfaces, InterfaceService)
        result = service.ip_in_use({
            'ipv4': True,
            'ipv6': True,
            'ipv6_link_local': False,
            'loopback': False,
            'any': False,
            'static': False,
        })

        # Should get IPs from en0 and en1, but not tap0 (internal) or lo0 (not requested)
        addresses = [ip['address'] for ip in result]
        assert '192.168.1.10' in addresses  # en0 IPv4
        assert '10.0.0.10' in addresses     # en1 IPv4
        assert '2001:db8::1' in addresses   # en0 IPv6
        assert '2001:db8::2' in addresses   # en1 IPv6
        assert 'fe80::1' not in addresses   # link-local filtered
        assert '172.16.0.1' not in addresses  # tap interface ignored


def test_ip_in_use_with_single_interface(middleware_with_interfaces, mock_interfaces):
    """Test filtering by a single interface."""
    with patch('middlewared.plugins.network.netif') as mock_netif:
        mock_netif.list_interfaces = Mock(return_value=mock_interfaces)

        service = create_service(middleware_with_interfaces, InterfaceService)
        result = service.ip_in_use({
            'ipv4': True,
            'ipv6': True,
            'ipv6_link_local': False,
            'loopback': False,
            'any': False,
            'static': False,
            'interfaces': ['en0'],
        })

        # Should only get IPs from en0
        addresses = [ip['address'] for ip in result]
        assert '192.168.1.10' in addresses  # en0 IPv4
        assert '2001:db8::1' in addresses   # en0 IPv6
        assert '10.0.0.10' not in addresses  # en1 IPv4 should not be included
        assert '2001:db8::2' not in addresses  # en1 IPv6 should not be included


def test_ip_in_use_with_multiple_interfaces(middleware_with_interfaces, mock_interfaces):
    """Test filtering by multiple interfaces."""
    with patch('middlewared.plugins.network.netif') as mock_netif:
        mock_netif.list_interfaces = Mock(return_value=mock_interfaces)

        service = create_service(middleware_with_interfaces, InterfaceService)
        result = service.ip_in_use({
            'ipv4': True,
            'ipv6': True,
            'ipv6_link_local': False,
            'loopback': False,
            'any': False,
            'static': False,
            'interfaces': ['en0', 'en1'],
        })

        # Should get IPs from both en0 and en1
        addresses = [ip['address'] for ip in result]
        assert '192.168.1.10' in addresses  # en0 IPv4
        assert '10.0.0.10' in addresses     # en1 IPv4
        assert '2001:db8::1' in addresses   # en0 IPv6
        assert '2001:db8::2' in addresses   # en1 IPv6


def test_ip_in_use_with_empty_interfaces_list(middleware_with_interfaces, mock_interfaces):
    """Test that empty interfaces list behaves like default (all interfaces)."""
    with patch('middlewared.plugins.network.netif') as mock_netif:
        mock_netif.list_interfaces = Mock(return_value=mock_interfaces)

        service = create_service(middleware_with_interfaces, InterfaceService)
        result = service.ip_in_use({
            'ipv4': True,
            'ipv6': True,
            'ipv6_link_local': False,
            'loopback': False,
            'any': False,
            'static': False,
            'interfaces': [],
        })

        # Should behave like default - get IPs from all non-internal interfaces
        addresses = [ip['address'] for ip in result]
        assert '192.168.1.10' in addresses  # en0 IPv4
        assert '10.0.0.10' in addresses     # en1 IPv4
        assert '2001:db8::1' in addresses   # en0 IPv6
        assert '2001:db8::2' in addresses   # en1 IPv6


def test_ip_in_use_with_nonexistent_interface(middleware_with_interfaces, mock_interfaces):
    """Test that non-existent interface names are ignored."""
    with patch('middlewared.plugins.network.netif') as mock_netif:
        mock_netif.list_interfaces = Mock(return_value=mock_interfaces)

        service = create_service(middleware_with_interfaces, InterfaceService)
        result = service.ip_in_use({
            'ipv4': True,
            'ipv6': True,
            'ipv6_link_local': False,
            'loopback': False,
            'any': False,
            'static': False,
            'interfaces': ['nonexistent', 'en0'],
        })

        # Should only get IPs from en0 (nonexistent is ignored)
        addresses = [ip['address'] for ip in result]
        assert '192.168.1.10' in addresses  # en0 IPv4
        assert '2001:db8::1' in addresses   # en0 IPv6
        assert len(result) == 2  # Only IPs from en0


def test_ip_in_use_with_loopback_and_interface_filter(middleware_with_interfaces, mock_interfaces):
    """Test combining loopback option with interface filtering."""
    # Mock interface.internal_interfaces to include 'lo' so it can be removed
    middleware_with_interfaces['interface.internal_interfaces'] = Mock(return_value=['tap', 'epair', 'lo'])

    with patch('middlewared.plugins.network.netif') as mock_netif:
        mock_netif.list_interfaces = Mock(return_value=mock_interfaces)

        service = create_service(middleware_with_interfaces, InterfaceService)
        result = service.ip_in_use({
            'ipv4': True,
            'ipv6': True,
            'ipv6_link_local': False,
            'loopback': True,
            'any': False,
            'static': False,
            'interfaces': ['lo0', 'en0'],
        })

        # Should get IPs from lo0 and en0
        addresses = [ip['address'] for ip in result]
        assert '127.0.0.1' in addresses     # lo0 IPv4
        assert '::1' in addresses           # lo0 IPv6
        assert '192.168.1.10' in addresses  # en0 IPv4
        assert '2001:db8::1' in addresses   # en0 IPv6


def test_ip_in_use_with_static_filter_and_interfaces(middleware_with_interfaces, mock_interfaces):
    """Test combining static IP filter with interface filtering."""
    with patch('middlewared.plugins.network.netif') as mock_netif:
        mock_netif.list_interfaces = Mock(return_value=mock_interfaces)

        service = create_service(middleware_with_interfaces, InterfaceService)
        result = service.ip_in_use({
            'ipv4': True,
            'ipv6': True,
            'ipv6_link_local': False,
            'loopback': False,
            'any': False,
            'static': True,
            'interfaces': ['en0', 'en1'],
        })

        # Should only get static IPs from specified interfaces
        addresses = [ip['address'] for ip in result]
        assert '192.168.1.10' in addresses  # en0 static IPv4
        assert '10.0.0.10' in addresses     # en1 static IPv4
        assert '2001:db8::1' in addresses   # en0 static IPv6
        # en1 IPv6 is not in the static config, so should not appear


def test_ip_in_use_ipv6_link_local_with_interfaces(middleware_with_interfaces, mock_interfaces):
    """Test IPv6 link-local filtering with interface specification."""
    with patch('middlewared.plugins.network.netif') as mock_netif:
        mock_netif.list_interfaces = Mock(return_value=mock_interfaces)

        service = create_service(middleware_with_interfaces, InterfaceService)

        # First without link-local
        result = service.ip_in_use({
            'ipv4': False,
            'ipv6': True,
            'ipv6_link_local': False,
            'loopback': False,
            'any': False,
            'static': False,
            'interfaces': ['en0'],
        })

        addresses = [ip['address'] for ip in result]
        assert '2001:db8::1' in addresses
        assert 'fe80::1' not in addresses

        # Now with link-local
        result = service.ip_in_use({
            'ipv4': False,
            'ipv6': True,
            'ipv6_link_local': True,
            'loopback': False,
            'any': False,
            'static': False,
            'interfaces': ['en0'],
        })

        addresses = [ip['address'] for ip in result]
        assert '2001:db8::1' in addresses
        assert 'fe80::1' in addresses


def test_ip_in_use_any_option_not_affected_by_interfaces(middleware_with_interfaces, mock_interfaces):
    """Test that 'any' addresses (0.0.0.0, ::) are not affected by interface filter."""
    with patch('middlewared.plugins.network.netif') as mock_netif:
        mock_netif.list_interfaces = Mock(return_value=mock_interfaces)

        service = create_service(middleware_with_interfaces, InterfaceService)
        result = service.ip_in_use({
            'ipv4': True,
            'ipv6': True,
            'ipv6_link_local': False,
            'loopback': False,
            'any': True,
            'static': False,
            'interfaces': ['en0'],  # Should not affect 'any' addresses
        })

        addresses = [ip['address'] for ip in result]
        assert '0.0.0.0' in addresses       # Any IPv4
        assert '::' in addresses            # Any IPv6
        assert '192.168.1.10' in addresses  # en0 IPv4
        assert '2001:db8::1' in addresses   # en0 IPv6

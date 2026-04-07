import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from middlewared.service import ValidationErrors
from middlewared.plugins.truenas_connect.update import TrueNASConnectService
from middlewared.plugins.truenas_connect.hostname import TNCHostnameService
from middlewared.plugins.truenas_connect.utils import TNC_IPS_CACHE_KEY


@pytest.fixture
def tnc_service():
    """Create a mock TrueNASConnectService instance."""
    service = TrueNASConnectService(MagicMock())
    service.middleware.call2 = AsyncMock()
    return service


class TestTNCGetEffectiveIps:
    """Test get_effective_ips logic that derives IPs from system.general.config."""

    @pytest.mark.asyncio
    async def test_wildcard_ipv4(self, tnc_service):
        """When ui_address is 0.0.0.0, resolve to all IPv4 addresses via ip_in_use."""
        async def mock_call(method, *args, **kwargs):
            if method == 'system.general.config':
                return {'ui_address': ['0.0.0.0'], 'ui_v6address': ['2001:db8::1']}
            elif method == 'interface.ip_in_use':
                opts = args[0]
                assert opts['ipv4'] is True
                assert opts['ipv6'] is False
                assert opts['static'] is False
                assert opts['loopback'] is False
                assert opts['any'] is False
                return [
                    {'address': '192.168.1.10'},
                    {'address': '10.0.0.10'},
                ]
            raise ValueError(f'Unexpected: {method}')

        tnc_service.middleware.call = AsyncMock(side_effect=mock_call)
        result = await tnc_service.get_effective_ips()
        assert set(result) == {'192.168.1.10', '10.0.0.10', '2001:db8::1'}

    @pytest.mark.asyncio
    async def test_wildcard_ipv6(self, tnc_service):
        """When ui_v6address is ::, resolve to all non-link-local IPv6 addresses."""
        async def mock_call(method, *args, **kwargs):
            if method == 'system.general.config':
                return {'ui_address': ['192.168.1.10'], 'ui_v6address': ['::']}
            elif method == 'interface.ip_in_use':
                opts = args[0]
                assert opts['ipv4'] is False
                assert opts['ipv6'] is True
                assert opts['ipv6_link_local'] is False
                assert opts['static'] is False
                return [
                    {'address': '2001:db8::1'},
                    {'address': '2001:db8::2'},
                ]
            raise ValueError(f'Unexpected: {method}')

        tnc_service.middleware.call = AsyncMock(side_effect=mock_call)
        result = await tnc_service.get_effective_ips()
        assert set(result) == {'192.168.1.10', '2001:db8::1', '2001:db8::2'}

    @pytest.mark.asyncio
    async def test_both_wildcards(self, tnc_service):
        """When both are wildcards, resolve all IPv4 and IPv6."""
        call_count = {'ipv4': 0, 'ipv6': 0}

        async def mock_call(method, *args, **kwargs):
            if method == 'system.general.config':
                return {'ui_address': ['0.0.0.0'], 'ui_v6address': ['::']}
            elif method == 'interface.ip_in_use':
                opts = args[0]
                if opts['ipv4']:
                    call_count['ipv4'] += 1
                    return [{'address': '192.168.1.10'}]
                else:
                    call_count['ipv6'] += 1
                    return [{'address': '2001:db8::1'}]
            raise ValueError(f'Unexpected: {method}')

        tnc_service.middleware.call = AsyncMock(side_effect=mock_call)
        result = await tnc_service.get_effective_ips()
        assert set(result) == {'192.168.1.10', '2001:db8::1'}
        assert call_count['ipv4'] == 1
        assert call_count['ipv6'] == 1

    @pytest.mark.asyncio
    async def test_specific_ips(self, tnc_service):
        """When specific IPs are configured, use them directly without calling ip_in_use."""
        async def mock_call(method, *args, **kwargs):
            if method == 'system.general.config':
                return {'ui_address': ['192.168.1.10'], 'ui_v6address': ['2001:db8::1']}
            elif method == 'interface.ip_in_use':
                raise AssertionError('ip_in_use should not be called for specific IPs')
            raise ValueError(f'Unexpected: {method}')

        tnc_service.middleware.call = AsyncMock(side_effect=mock_call)
        result = await tnc_service.get_effective_ips()
        assert result == ['192.168.1.10', '2001:db8::1']

    @pytest.mark.asyncio
    async def test_mixed_wildcard_v4_specific_v6(self, tnc_service):
        """Wildcard IPv4 + specific IPv6."""
        async def mock_call(method, *args, **kwargs):
            if method == 'system.general.config':
                return {'ui_address': ['0.0.0.0'], 'ui_v6address': ['2001:db8::1']}
            elif method == 'interface.ip_in_use':
                opts = args[0]
                assert opts['ipv4'] is True
                assert opts['ipv6'] is False
                return [{'address': '10.0.0.5'}, {'address': '172.16.0.1'}]
            raise ValueError(f'Unexpected: {method}')

        tnc_service.middleware.call = AsyncMock(side_effect=mock_call)
        result = await tnc_service.get_effective_ips()
        assert set(result) == {'10.0.0.5', '172.16.0.1', '2001:db8::1'}

    @pytest.mark.asyncio
    async def test_wildcard_resolves_to_empty(self, tnc_service):
        """When wildcards resolve to no IPs (no interfaces up), return empty list."""
        async def mock_call(method, *args, **kwargs):
            if method == 'system.general.config':
                return {'ui_address': ['0.0.0.0'], 'ui_v6address': ['::']}
            elif method == 'interface.ip_in_use':
                return []
            raise ValueError(f'Unexpected: {method}')

        tnc_service.middleware.call = AsyncMock(side_effect=mock_call)
        result = await tnc_service.get_effective_ips()
        assert result == []


class TestTNCValidation:
    """Test TNC validation logic."""

    @pytest.mark.asyncio
    async def test_validate_ha_requires_vips(self, tnc_service):
        """On HA systems, enabling TNC requires VIPs to exist."""
        async def mock_call(method, *args, **kwargs):
            if method == 'system.is_ha_capable':
                return True
            elif method == 'interface.query':
                return [{'failover_virtual_aliases': []}]
            raise ValueError(f'Unexpected: {method}')

        tnc_service.middleware.call = AsyncMock(side_effect=mock_call)

        with pytest.raises(ValidationErrors) as exc_info:
            await tnc_service.validate_data({'enabled': True})

        assert 'HA systems must be in a healthy state' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_non_ha_requires_effective_ips(self, tnc_service):
        """On non-HA systems, enabling TNC requires at least one effective IP."""
        async def mock_call(method, *args, **kwargs):
            if method == 'system.is_ha_capable':
                return False
            elif method == 'system.general.config':
                return {'ui_address': ['0.0.0.0'], 'ui_v6address': ['::']}
            elif method == 'interface.ip_in_use':
                return []
            raise ValueError(f'Unexpected: {method}')

        tnc_service.middleware.call = AsyncMock(side_effect=mock_call)

        with pytest.raises(ValidationErrors) as exc_info:
            await tnc_service.validate_data({'enabled': True})

        assert 'at least one IP address' in str(exc_info.value)

    @pytest.mark.asyncio
<<<<<<< HEAD
    async def test_validate_data_use_all_interfaces_no_ips_or_interfaces(self, tnc_service, mock_interfaces):
        """Test that use_all_interfaces=True allows enabling without specific IPs or interfaces."""
        # Mock system.is_ha_capable to return False for non-HA systems
        tnc_service.middleware.call = AsyncMock(return_value=False)

        old_config = {
            'enabled': False, 'ips': [], 'interfaces': [], 'status': Status.DISABLED.name,
            'use_all_interfaces': True
        }
        data = {'enabled': True, 'ips': [], 'interfaces': [], 'use_all_interfaces': True}

        # Should not raise any errors
        await tnc_service.validate_data(old_config, data)

    @pytest.mark.asyncio
    async def test_validate_data_use_all_interfaces_false_requires_ips_or_interfaces(self, tnc_service):
        """Test that use_all_interfaces=False requires at least one IP or interface."""
        # Mock system.is_ha_capable to return False for non-HA systems
        tnc_service.middleware.call = AsyncMock(return_value=False)

        old_config = {
            'enabled': False, 'ips': [], 'interfaces': [], 'status': Status.DISABLED.name,
            'use_all_interfaces': True
        }
        data = {'enabled': True, 'ips': [], 'interfaces': [], 'use_all_interfaces': False}

        with pytest.raises(ValidationErrors) as exc_info:
            await tnc_service.validate_data(old_config, data)

        assert 'At least one IP or interface must be provided' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_all_interface_ips(self, tnc_service, mock_interfaces):
        """Test that get_all_interface_ips retrieves IPs from all interfaces."""
        # Mock interface.query to return all interfaces
        mock_interface_names = [{'name': 'ens3'}, {'name': 'ens4'}, {'name': 'ens5'}]

        # Mock interface.ip_in_use to return IPs
        mock_ips = [
            {'type': 'INET', 'address': '192.168.1.10'},
            {'type': 'INET6', 'address': '2001:db8::1'},
            {'type': 'INET', 'address': '10.0.0.10'},
        ]

        async def mock_middleware_call(method, *args, **kwargs):
            if method == 'interface.query':
                return mock_interface_names
            elif method == 'interface.ip_in_use':
                # Check that all interfaces were requested
                # The interfaces are passed as the first positional argument in a dict
                if args and 'interfaces' in args[0]:
                    assert set(args[0]['interfaces']) == {'ens3', 'ens4', 'ens5'}
                return mock_ips
            else:
                raise ValueError(f"Unexpected middleware.call: {method}")

        tnc_service.middleware.call = AsyncMock(side_effect=mock_middleware_call)

        result = await tnc_service.get_all_interface_ips()
        assert set(result) == {'192.168.1.10', '2001:db8::1', '10.0.0.10'}

    @pytest.mark.asyncio
    async def test_do_update_use_all_interfaces_true(self, tnc_service):
        """Test that do_update uses all interfaces when use_all_interfaces=True."""
        # Mock the config method
        tnc_service.config = AsyncMock(return_value={
            'id': 1,
            'enabled': False,
            'ips': [],
            'interfaces': ['ens3'],  # Has configured interface
            'use_all_interfaces': False,
            'status': Status.DISABLED.name,
            'interfaces_ips': [],
            'account_service_base_url': 'https://example.com/',
            'leca_service_base_url': 'https://example.com/',
            'tnc_base_url': 'https://example.com/',
            'heartbeat_url': 'https://example.com/'
        })

        # Keep track of which method was called and with what parameters
        interface_query_called = False
        interface_ip_in_use_called = False
        requested_interfaces = None

        async def mock_middleware_call(method, *args, **kwargs):
            nonlocal interface_query_called, interface_ip_in_use_called, requested_interfaces

            if method == 'interface.query':
                # This is called by get_all_interface_ips
                interface_query_called = True
                return [{'name': 'ens3'}, {'name': 'ens4'}, {'name': 'ens5'}]
            elif method == 'interface.ip_in_use':
                # This is called by get_interface_ips
                interface_ip_in_use_called = True
                if args and 'interfaces' in args[0]:
                    requested_interfaces = args[0]['interfaces']
                return [
                    {'type': 'INET', 'address': '192.168.1.10'},
                    {'type': 'INET', 'address': '10.0.0.10'},
                    {'type': 'INET', 'address': '172.16.0.10'},
                ]
            elif method in ['cache.pop']:
                return None
            elif method == 'datastore.update':
                # Verify that interfaces_ips was updated with all IPs
                assert args[2]['interfaces_ips'] == ['192.168.1.10', '10.0.0.10', '172.16.0.10']
                return None
            else:
                return None

        tnc_service.middleware.call = AsyncMock(side_effect=mock_middleware_call)
        tnc_service.validate_data = AsyncMock()

        # Update with use_all_interfaces=True
        await tnc_service.do_update({
            'enabled': True,
            'ips': [],
            'interfaces': ['ens3'],
            'use_all_interfaces': True
        })

        # Verify that get_all_interface_ips was called (which calls interface.query)
        assert interface_query_called
        assert interface_ip_in_use_called
        # Verify that all interfaces were requested
        assert set(requested_interfaces) == {'ens3', 'ens4', 'ens5'}


class TestTNCInterfacesUpdate:
    """Test update logic for interfaces."""

    @pytest.mark.asyncio
    async def test_do_update_extracts_interface_ips(self, tnc_service, mock_interfaces):
        """Test that do_update properly extracts IPs from selected interfaces."""
        tnc_service.middleware.call = AsyncMock()

        # Mock the config method
        tnc_service.config = AsyncMock(return_value={
            'id': 1,
            'enabled': False,
            'ips': [],
            'interfaces': [],
            'status': Status.DISABLED.name,
            'interfaces_ips': [],
            'use_all_interfaces': True,
            'account_service_base_url': 'https://example.com/',
            'leca_service_base_url': 'https://example.com/',
            'tnc_base_url': 'https://example.com/',
            'heartbeat_url': 'https://example.com/'
        })

        # When retrieve_names_only=True, interface.query returns only names
        mock_interface_names = [{'name': 'ens3'}, {'name': 'ens4'}, {'name': 'ens5'}]

        # Create a function that handles the calls appropriately
        def mock_middleware_call(method, *args, **kwargs):
=======
    async def test_validate_passes_with_effective_ips(self, tnc_service):
        """Validation passes when effective IPs are available."""
        async def mock_call(method, *args, **kwargs):
>>>>>>> e051b5507e (Remove ips/interfaces fields from tnc configuration)
            if method == 'system.is_ha_capable':
                return False
            elif method == 'system.general.config':
                return {'ui_address': ['192.168.1.10'], 'ui_v6address': ['::']}
            elif method == 'interface.ip_in_use':
<<<<<<< HEAD
                # Return IPs for the requested interfaces
                return [
                    {'type': 'INET', 'address': '192.168.1.10', 'netmask': 24},
                    {'type': 'INET6', 'address': '2001:db8::1', 'netmask': 64},
                    {'type': 'INET', 'address': '10.0.0.10', 'netmask': 24},
                ]
            elif method == 'cache.pop':
                return None
            elif method == 'datastore.update':
                return None
            else:
                raise ValueError(f"Unexpected middleware.call: {method}")
=======
                return [{'address': '2001:db8::1'}]
            raise ValueError(f'Unexpected: {method}')
>>>>>>> e051b5507e (Remove ips/interfaces fields from tnc configuration)

        tnc_service.middleware.call = AsyncMock(side_effect=mock_call)
        # Should not raise
        await tnc_service.validate_data({'enabled': True})

    @pytest.mark.asyncio
    async def test_validate_skips_when_disabled(self, tnc_service):
        """No IP validation when TNC is being disabled."""
        tnc_service.middleware.call = AsyncMock()
<<<<<<< HEAD

        # Mock the config method
        tnc_service.config = AsyncMock(return_value={
            'id': 1,
            'enabled': False,
            'ips': [],
            'interfaces': [],
            'status': Status.DISABLED.name,
            'interfaces_ips': [],
            'use_all_interfaces': True,
            'account_service_base_url': 'https://example.com/',
            'leca_service_base_url': 'https://example.com/',
            'tnc_base_url': 'https://example.com/',
            'heartbeat_url': 'https://example.com/'
        })

        # When retrieve_names_only=True, interface.query returns only names
        mock_interface_names = [{'name': 'ens6'}]

        # Create a function that handles the calls appropriately
        def mock_middleware_call(method, *args, **kwargs):
            if method == 'system.is_ha_capable':
                return False
            elif method == 'interface.query':
                return mock_interface_names
            elif method == 'interface.ip_in_use':
                # Return IPs for the requested interfaces (already filters link-local)
                return [
                    {'type': 'INET', 'address': '192.168.2.10', 'netmask': 24},
                    {'type': 'INET6', 'address': '2001:db8::2', 'netmask': 64},
                ]
            elif method == 'cache.pop':
                return None
            elif method == 'datastore.update':
                return None
            else:
                raise ValueError(f"Unexpected middleware.call: {method}")

        tnc_service.middleware.call = AsyncMock(side_effect=mock_middleware_call)

        # Also need to mock the final config call
        tnc_service.config = AsyncMock()
        tnc_service.config.side_effect = [
            # First call returns initial config
            {
                'id': 1,
                'enabled': False,
                'ips': [],
                'interfaces': [],
                'status': Status.DISABLED.name,
                'interfaces_ips': [],
                'use_all_interfaces': True,
                'account_service_base_url': 'https://example.com/',
                'leca_service_base_url': 'https://example.com/',
                'tnc_base_url': 'https://example.com/',
                'heartbeat_url': 'https://example.com/'
            },
            # Second call returns updated config
            {
                'id': 1,
                'enabled': True,
                'ips': [],
                'interfaces': ['ens6'],
                'interfaces_ips': ['192.168.2.10', '2001:db8::2'],
                'status': 'CLAIM_TOKEN_MISSING',
                'status_reason': 'Claim token is missing',
                'certificate': None,
                'use_all_interfaces': False,
                'account_service_base_url': 'https://example.com/',
                'leca_service_base_url': 'https://example.com/',
                'tnc_base_url': 'https://example.com/',
                'heartbeat_url': 'https://example.com/',
            }
        ]

        tnc_service.middleware.send_event = MagicMock()

        data = {
            'enabled': True,
            'ips': [],
            'interfaces': ['ens6'],
            'use_all_interfaces': False
        }

        # Track the datastore.update call
        db_update_payload = {}

        # Update the mock to capture datastore.update payload
        original_mock = tnc_service.middleware.call.side_effect

        def capture_middleware_call(method, *args, **kwargs):
            if method == 'datastore.update':
                nonlocal db_update_payload
                db_update_payload = args[2]  # Third argument is the payload
            return original_mock(method, *args, **kwargs)

        tnc_service.middleware.call.side_effect = capture_middleware_call

        await tnc_service.do_update(data)

        # Check that link-local IPv6 was filtered out
        assert set(db_update_payload['interfaces_ips']) == {'192.168.2.10', '2001:db8::2'}
        assert 'fe80::1234:5678:90ab:cdef' not in db_update_payload['interfaces_ips']

    @pytest.mark.asyncio
    async def test_do_update_combined_ips_registration(self, tnc_service, mock_interfaces):
        """Test that hostname registration uses combined IPs."""
        tnc_service.middleware.call = AsyncMock()

        # Mock the config method
        tnc_service.config = AsyncMock(return_value={
            'id': 1,
            'enabled': True,
            'ips': ['192.168.1.100'],
            'interfaces': ['ens3'],
            'interfaces_ips': ['192.168.1.10'],
            'status': Status.CONFIGURED.name,
            'use_all_interfaces': False,  # Set to False to use specific interfaces
            'account_service_base_url': 'https://example.com/',
            'leca_service_base_url': 'https://example.com/',
            'tnc_base_url': 'https://example.com/',
            'heartbeat_url': 'https://example.com/'
        })

        # When retrieve_names_only=True, interface.query returns only names
        mock_interface_names = [{'name': 'ens3'}, {'name': 'ens4'}, {'name': 'ens5'}]

        tnc_service.middleware.call.side_effect = [
            # system.is_ha_capable() call - return False for non-HA
            False,
            # interface.query() call in validate_data with retrieve_names_only=True
            mock_interface_names,
            # interface.ip_in_use() call in do_update (for ens4)
            [
                {'type': 'INET', 'address': '10.0.0.10', 'netmask': 24},
            ],
            # cache.pop() call for TNC_IPS_CACHE_KEY
            None,
            # hostname.register_update_ips() call
            {'error': None},
            # datastore.update() call
            None,
        ]

        tnc_service.middleware.send_event = MagicMock()

        data = {
            'enabled': True,
            'ips': ['192.168.1.100'],
            'interfaces': ['ens4'],
            'use_all_interfaces': False  # Explicitly set to False
        }

        await tnc_service.do_update(data)

        # Verify hostname.register_update_ips was called with combined IPs
        register_call = tnc_service.middleware.call.call_args_list[4]  # Updated index after system.is_ha_capable
        assert register_call[0][0] == 'tn_connect.hostname.register_update_ips'
        combined_ips = register_call[0][1]
        assert set(combined_ips) == {'192.168.1.100', '10.0.0.10'}
=======
        # Should not raise regardless of IP state
        await tnc_service.validate_data({'enabled': False})
>>>>>>> e051b5507e (Remove ips/interfaces fields from tnc configuration)


class TestTNCHostnameService:
    """Test hostname service updates."""

    @pytest.mark.asyncio
    async def test_register_update_ips_uses_effective_ips(self):
        """Test that register_update_ips calls get_effective_ips when no IPs provided."""
        service = TNCHostnameService(MagicMock())

        def mock_middleware_call(method, *args, **kwargs):
            if method == 'tn_connect.config_internal':
                return {'jwt_token': 'test_token'}
            elif method == 'tn_connect.get_effective_ips':
                return ['192.168.1.10', '2001:db8::1']
            elif method == 'system.is_ha_capable':
                return False
            return None

        service.middleware.call = AsyncMock(side_effect=mock_middleware_call)

        with patch('middlewared.plugins.truenas_connect.hostname.register_update_ips',
                   new_callable=AsyncMock) as mock_register:
            mock_register.return_value = {}
            await service.register_update_ips()

            mock_register.assert_called_once()
            called_ips = mock_register.call_args[0][1]
            assert set(called_ips) == {'192.168.1.10', '2001:db8::1'}

    @pytest.mark.asyncio
    async def test_register_update_ips_with_explicit_ips(self):
        """Test that register_update_ips uses provided IPs when specified."""
        service = TNCHostnameService(MagicMock())

        def mock_middleware_call(method, *args, **kwargs):
            if method == 'tn_connect.config_internal':
                return {'jwt_token': 'test_token'}
            elif method == 'system.is_ha_capable':
                return False
            return None

        service.middleware.call = AsyncMock(side_effect=mock_middleware_call)

        with patch('middlewared.plugins.truenas_connect.hostname.register_update_ips',
                   new_callable=AsyncMock) as mock_register:
            mock_register.return_value = {}
            explicit_ips = ['1.2.3.4', '5.6.7.8']
            await service.register_update_ips(explicit_ips)

            mock_register.assert_called_once()
            called_ips = mock_register.call_args[0][1]
            assert called_ips == explicit_ips

    @pytest.mark.asyncio
    async def test_register_update_ips_ha_prepends_vips(self):
        """Test that HA systems prepend VIPs to the IP list."""
        service = TNCHostnameService(MagicMock())

        def mock_middleware_call(method, *args, **kwargs):
            if method == 'tn_connect.config_internal':
                return {'jwt_token': 'test_token'}
            elif method == 'tn_connect.get_effective_ips':
                return ['192.168.1.10']
            elif method == 'system.is_ha_capable':
                return True
            elif method == 'tn_connect.ha_vips':
                return ['10.0.0.100']
            return None

        service.middleware.call = AsyncMock(side_effect=mock_middleware_call)

        with patch('middlewared.plugins.truenas_connect.hostname.register_update_ips',
                   new_callable=AsyncMock) as mock_register:
            mock_register.return_value = {}
            await service.register_update_ips()

            called_ips = mock_register.call_args[0][1]
            # VIPs should be first
            assert called_ips == ['10.0.0.100', '192.168.1.10']

    @pytest.mark.asyncio
    async def test_sync_ips_skips_when_no_wildcards(self):
        """Test that network events are ignored when system.general has only specific IPs."""
        service = TNCHostnameService(MagicMock())
        service.config = AsyncMock()

        async def mock_middleware_call(method, *args, **kwargs):
            if method == 'failover.is_single_master_node':
                return True
            elif method == 'tn_connect.config':
                return {'id': 1, 'status': 'CONFIGURED'}
            elif method == 'system.general.config':
                return {'ui_address': ['192.168.1.10'], 'ui_v6address': ['2001:db8::1']}
            elif method == 'tn_connect.get_effective_ips':
                raise AssertionError('get_effective_ips should not be called')
            raise ValueError(f'Unexpected: {method}')

        service.middleware.call = AsyncMock(side_effect=mock_middleware_call)

        # With event_details, should skip when no wildcards
        await service.sync_ips(event_details={'type': 'ipaddress.change', 'iface': 'ens3'})

    @pytest.mark.asyncio
    async def test_sync_ips_proceeds_with_wildcards(self):
        """Test that network events trigger sync when wildcards are configured."""
        service = TNCHostnameService(MagicMock())
        service.config = AsyncMock(return_value={})

        register_called = False

        async def mock_middleware_call(method, *args, **kwargs):
            nonlocal register_called
            if method == 'failover.is_single_master_node':
                return True
            elif method == 'tn_connect.config':
                return {'id': 1, 'status': 'CONFIGURED'}
            elif method == 'system.general.config':
                return {'ui_address': ['0.0.0.0'], 'ui_v6address': ['::']}
            elif method == 'tn_connect.get_effective_ips':
                return ['192.168.1.10', '2001:db8::1']
            elif method == 'cache.get':
                raise KeyError('miss')
            elif method == 'tn_connect.hostname.register_update_ips':
                register_called = True
                return {'error': None}
            elif method == 'cache.put':
                return None
            return None

        service.middleware.call = AsyncMock(side_effect=mock_middleware_call)
        service.middleware.call_hook = AsyncMock()

        await service.sync_ips(event_details={'type': 'ipaddress.change', 'iface': 'ens3'})
        assert register_called

    @pytest.mark.asyncio
    async def test_sync_ips_skips_when_cached(self):
        """Test that sync is skipped when cached IPs match current IPs."""
        service = TNCHostnameService(MagicMock())
        service.config = AsyncMock()

        async def mock_middleware_call(method, *args, **kwargs):
            if method == 'failover.is_single_master_node':
                return True
            elif method == 'tn_connect.config':
                return {'id': 1, 'status': 'CONFIGURED'}
            elif method == 'tn_connect.get_effective_ips':
                return ['192.168.1.10']
            elif method == 'cache.get':
                return ['192.168.1.10']
            elif method == 'tn_connect.hostname.register_update_ips':
                raise AssertionError('Should not sync when cached IPs match')
            return None

        service.middleware.call = AsyncMock(side_effect=mock_middleware_call)
        # No event_details = no wildcard check, goes straight to resolve + cache compare
        await service.sync_ips()

    @pytest.mark.asyncio
    async def test_sync_ips_empty_effective_ips_skips_http(self):
        """Test that sync skips HTTP call when effective IPs are empty."""
        service = TNCHostnameService(MagicMock())
        service.config = AsyncMock()

        register_called = False
        cache_put_args = None

        async def mock_middleware_call(method, *args, **kwargs):
            nonlocal register_called, cache_put_args
            if method == 'failover.is_single_master_node':
                return True
            elif method == 'tn_connect.config':
                return {'id': 1, 'status': 'CONFIGURED'}
            elif method == 'tn_connect.get_effective_ips':
                return []
            elif method == 'cache.get':
                raise KeyError('miss')
            elif method == 'tn_connect.hostname.register_update_ips':
                register_called = True
                return {'error': None}
            elif method == 'cache.put':
                cache_put_args = args
                return None
            return None

        service.middleware.call = AsyncMock(side_effect=mock_middleware_call)
        service.middleware.call_hook = AsyncMock()

        await service.sync_ips()

        assert not register_called
        assert cache_put_args is not None
        assert cache_put_args[0] == TNC_IPS_CACHE_KEY
        assert cache_put_args[1] == []
        service.middleware.call_hook.assert_not_called()

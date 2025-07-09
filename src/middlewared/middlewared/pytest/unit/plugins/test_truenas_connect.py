import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from middlewared.service import ValidationErrors
from middlewared.plugins.truenas_connect.update import TrueNASConnectService
from middlewared.plugins.truenas_connect.hostname import TNCHostnameService
from truenas_connect_utils.status import Status


@pytest.fixture
def tnc_service():
    """Create a mock TrueNASConnectService instance."""
    service = TrueNASConnectService(None)
    service.middleware = MagicMock()
    return service


@pytest.fixture
def mock_interfaces():
    """Mock interface.query response."""
    return [
        {
            'id': 'ens3',
            'state': {
                'aliases': [
                    {'type': 'INET', 'address': '192.168.1.10'},
                    {'type': 'INET6', 'address': 'fe80::1'},
                    {'type': 'INET6', 'address': '2001:db8::1'},
                ]
            }
        },
        {
            'id': 'ens4',
            'state': {
                'aliases': [
                    {'type': 'INET', 'address': '10.0.0.10'},
                ]
            }
        },
        {
            'id': 'ens5',
            'state': {
                'aliases': []
            }
        }
    ]


class TestTNCInterfacesValidation:
    """Test validation logic for interfaces."""

    @pytest.mark.asyncio
    async def test_validate_data_requires_ip_or_interface(self, tnc_service):
        """Test that at least one IP or interface is required when enabled."""
        old_config = {
            'enabled': False, 'ips': [], 'interfaces': [], 'status': Status.DISABLED.name,
            'use_all_interfaces': True
        }
        data = {'enabled': True, 'ips': [], 'interfaces': [], 'use_all_interfaces': False}

        with pytest.raises(ValidationErrors) as exc_info:
            await tnc_service.validate_data(old_config, data)

        assert 'At least one IP or interface must be provided' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_data_interface_exists(self, tnc_service, mock_interfaces):
        """Test validation of interface existence."""
        # When retrieve_names_only=True, interface.query returns only names
        mock_interface_names = [{'name': 'ens3'}, {'name': 'ens4'}, {'name': 'ens5'}]

        # Create a function that handles the calls appropriately
        def mock_middleware_call(method, *args, **kwargs):
            if method == 'interface.query':
                return mock_interface_names
            elif method == 'interface.ip_in_use':
                # Return empty list since we're testing interface validation error
                return []
            else:
                raise ValueError(f"Unexpected middleware.call: {method}")

        tnc_service.middleware.call = AsyncMock(side_effect=mock_middleware_call)

        old_config = {
            'enabled': False, 'ips': [], 'interfaces': [], 'status': Status.DISABLED.name,
            'use_all_interfaces': True
        }
        data = {'enabled': True, 'ips': [], 'interfaces': ['ens3', 'invalid_interface'], 'use_all_interfaces': False}

        with pytest.raises(ValidationErrors) as exc_info:
            await tnc_service.validate_data(old_config, data)

        assert 'Interface "invalid_interface" does not exist' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_data_interface_has_ip(self, tnc_service, mock_interfaces):
        """Test that selected interfaces must have at least one IP when no direct IPs provided."""
        # When retrieve_names_only=True, interface.query returns only names
        mock_interface_names = [{'name': 'ens3'}, {'name': 'ens4'}, {'name': 'ens5'}]
        tnc_service.middleware.call = AsyncMock()
        tnc_service.middleware.call.side_effect = [
            # interface.query() call with retrieve_names_only=True
            mock_interface_names,
            # interface.ip_in_use() call - returns empty list for ens5
            [],
        ]

        old_config = {
            'enabled': False, 'ips': [], 'interfaces': [], 'status': Status.DISABLED.name,
            'use_all_interfaces': True
        }
        data = {'enabled': True, 'ips': [], 'interfaces': ['ens5'], 'use_all_interfaces': False}  # ens5 has no IPs

        with pytest.raises(ValidationErrors) as exc_info:
            await tnc_service.validate_data(old_config, data)

        assert 'Selected interfaces must have at least one IP address configured' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_data_interface_with_direct_ips(self, tnc_service, mock_interfaces):
        """Test that interface without IPs is allowed if direct IPs are provided."""
        # When retrieve_names_only=True, interface.query returns only names
        mock_interface_names = [{'name': 'ens3'}, {'name': 'ens4'}, {'name': 'ens5'}]
        tnc_service.middleware.call = AsyncMock(return_value=mock_interface_names)

        old_config = {
            'enabled': False, 'ips': [], 'interfaces': [], 'status': Status.DISABLED.name,
            'use_all_interfaces': True
        }
        data = {
            'enabled': True, 'ips': ['192.168.1.100'], 'interfaces': ['ens5'],
            'use_all_interfaces': False
        }  # ens5 has no IPs

        # Should not raise any errors
        await tnc_service.validate_data(old_config, data)

    @pytest.mark.asyncio
    async def test_validate_data_status_restriction(self, tnc_service, mock_interfaces):
        """Test that IPs/interfaces cannot be changed in certain states."""
        # When retrieve_names_only=True, interface.query returns only names
        mock_interface_names = [{'name': 'ens3'}, {'name': 'ens4'}, {'name': 'ens5'}]
        tnc_service.middleware.call = AsyncMock(return_value=mock_interface_names)

        old_config = {
            'enabled': True,
            'ips': ['192.168.1.10'],
            'interfaces': [],
            'status': Status.CERT_GENERATION_IN_PROGRESS.name,
            'use_all_interfaces': True,
            'account_service_base_url': 'https://example.com/',
            'leca_service_base_url': 'https://example.com/',
            'tnc_base_url': 'https://example.com/',
            'heartbeat_url': 'https://example.com/'
        }
        data = {
            'enabled': True,
            'ips': ['192.168.1.10'],
            'interfaces': ['ens3'],
            'use_all_interfaces': True,
            'account_service_base_url': 'https://example.com/',
            'leca_service_base_url': 'https://example.com/',
            'tnc_base_url': 'https://example.com/',
            'heartbeat_url': 'https://example.com/'
        }

        with pytest.raises(ValidationErrors) as exc_info:
            await tnc_service.validate_data(old_config, data)

        assert 'cannot be changed when TrueNAS Connect is in a state' in str(exc_info.value)


class TestTNCUseAllInterfaces:
    """Test use_all_interfaces functionality."""

    @pytest.mark.asyncio
    async def test_validate_data_use_all_interfaces_no_ips_or_interfaces(self, tnc_service, mock_interfaces):
        """Test that use_all_interfaces=True allows enabling without specific IPs or interfaces."""
        tnc_service.middleware.call = AsyncMock()

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
        tnc_service.middleware.call = AsyncMock()

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
            elif method in ['cache.pop', 'alert.oneshot_delete']:
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
            'use_all_interfaces': True,
            'account_service_base_url': 'https://example.com/',
            'leca_service_base_url': 'https://example.com/',
            'tnc_base_url': 'https://example.com/',
            'heartbeat_url': 'https://example.com/'
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
            if method == 'interface.query':
                return mock_interface_names
            elif method == 'interface.ip_in_use':
                # Return IPs for the requested interfaces
                return [
                    {'type': 'INET', 'address': '192.168.1.10', 'netmask': 24},
                    {'type': 'INET6', 'address': '2001:db8::1', 'netmask': 64},
                    {'type': 'INET', 'address': '10.0.0.10', 'netmask': 24},
                ]
            elif method == 'cache.pop':
                return None
            elif method == 'alert.oneshot_delete':
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
                'interfaces': ['ens3', 'ens4'],
                'interfaces_ips': ['192.168.1.10', '2001:db8::1', '10.0.0.10'],
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
            'interfaces': ['ens3', 'ens4'],
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

        # Check extracted IPs (should not include link-local IPv6)
        assert set(db_update_payload['interfaces_ips']) == {'192.168.1.10', '2001:db8::1', '10.0.0.10'}
        assert db_update_payload['interfaces'] == ['ens3', 'ens4']

    @pytest.mark.asyncio
    async def test_do_update_filters_link_local_ipv6(self, tnc_service):
        """Test that do_update filters out link-local IPv6 addresses."""
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
        mock_interface_names = [{'name': 'ens6'}]

        # Create a function that handles the calls appropriately
        def mock_middleware_call(method, *args, **kwargs):
            if method == 'interface.query':
                return mock_interface_names
            elif method == 'interface.ip_in_use':
                # Return IPs for the requested interfaces (already filters link-local)
                return [
                    {'type': 'INET', 'address': '192.168.2.10', 'netmask': 24},
                    {'type': 'INET6', 'address': '2001:db8::2', 'netmask': 64},
                ]
            elif method == 'cache.pop':
                return None
            elif method == 'alert.oneshot_delete':
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
            # interface.query() call in validate_data with retrieve_names_only=True
            mock_interface_names,
            # interface.ip_in_use() call in do_update (for ens4)
            [
                {'type': 'INET', 'address': '10.0.0.10', 'netmask': 24},
            ],
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
        register_call = tnc_service.middleware.call.call_args_list[2]
        assert register_call[0][0] == 'tn_connect.hostname.register_update_ips'
        combined_ips = register_call[0][1]
        assert set(combined_ips) == {'192.168.1.100', '10.0.0.10'}


class TestTNCHostnameService:
    """Test hostname service updates."""

    @pytest.mark.asyncio
    async def test_sync_interface_ips_use_all_interfaces_true(self):
        """Test that sync_interface_ips uses all interfaces when use_all_interfaces=True."""
        service = TNCHostnameService(None)
        service.middleware = MagicMock()

        # Track which methods were called
        get_all_called = False
        get_interfaces_called = False

        async def mock_middleware_call(method, *args, **kwargs):
            nonlocal get_all_called, get_interfaces_called

            if method == 'tn_connect.config':
                return {
                    'id': 1,
                    'interfaces': ['ens3'],
                    'use_all_interfaces': True
                }
            elif method == 'tn_connect.get_all_interface_ips':
                get_all_called = True
                return ['192.168.1.10', '10.0.0.10', '172.16.0.10']
            elif method == 'tn_connect.get_interface_ips':
                get_interfaces_called = True
                return ['192.168.1.10']
            elif method == 'datastore.update':
                # Verify all IPs were stored
                assert args[2]['interfaces_ips'] == ['192.168.1.10', '10.0.0.10', '172.16.0.10']
                return None
            elif method == 'tn_connect.hostname.register_update_ips':
                return {'error': None}
            else:
                return None

        service.middleware.call = AsyncMock(side_effect=mock_middleware_call)

        await service.sync_interface_ips()

        assert get_all_called
        assert not get_interfaces_called

    @pytest.mark.asyncio
    async def test_sync_interface_ips_use_all_interfaces_false(self):
        """Test that sync_interface_ips uses configured interfaces when use_all_interfaces=False."""
        service = TNCHostnameService(None)
        service.middleware = MagicMock()

        # Track which methods were called
        get_all_called = False
        get_interfaces_called = False

        async def mock_middleware_call(method, *args, **kwargs):
            nonlocal get_all_called, get_interfaces_called

            if method == 'tn_connect.config':
                return {
                    'id': 1,
                    'interfaces': ['ens3', 'ens4'],
                    'use_all_interfaces': False
                }
            elif method == 'tn_connect.get_all_interface_ips':
                get_all_called = True
                return ['192.168.1.10', '10.0.0.10', '172.16.0.10']
            elif method == 'tn_connect.get_interface_ips':
                get_interfaces_called = True
                assert args[0] == ['ens3', 'ens4']  # Verify correct interfaces passed
                return ['192.168.1.10', '10.0.0.10']
            elif method == 'datastore.update':
                # Verify only configured interface IPs were stored
                assert args[2]['interfaces_ips'] == ['192.168.1.10', '10.0.0.10']
                return None
            elif method == 'tn_connect.hostname.register_update_ips':
                return {'error': None}
            else:
                return None

        service.middleware.call = AsyncMock(side_effect=mock_middleware_call)

        await service.sync_interface_ips()

        assert not get_all_called
        assert get_interfaces_called

    @pytest.mark.asyncio
    async def test_register_update_ips_uses_combined_ips(self):
        """Test that register_update_ips uses combined IPs when no IPs provided."""
        from middlewared.plugins.truenas_connect.hostname import TNCHostnameService

        service = TNCHostnameService(None)
        service.middleware = MagicMock()
        service.middleware.call = AsyncMock(return_value={
            'ips': ['192.168.1.10'],
            'interfaces_ips': ['10.0.0.10', '172.16.0.10'],
            'jwt_token': 'test_token'
        })

        with patch('middlewared.plugins.truenas_connect.hostname.register_update_ips',
                   new_callable=AsyncMock) as mock_register:
            mock_register.return_value = {}

            await service.register_update_ips()

            # Verify the function was called with combined IPs
            mock_register.assert_called_once()
            called_ips = mock_register.call_args[0][1]
            assert set(called_ips) == {'192.168.1.10', '10.0.0.10', '172.16.0.10'}

    @pytest.mark.asyncio
    async def test_register_update_ips_with_explicit_ips(self):
        """Test that register_update_ips uses provided IPs when specified."""
        from middlewared.plugins.truenas_connect.hostname import TNCHostnameService

        service = TNCHostnameService(None)
        service.middleware = MagicMock()
        service.middleware.call = AsyncMock(return_value={
            'ips': ['192.168.1.10'],
            'interfaces_ips': ['10.0.0.10'],
            'jwt_token': 'test_token'
        })

        with patch('middlewared.plugins.truenas_connect.hostname.register_update_ips',
                   new_callable=AsyncMock) as mock_register:
            mock_register.return_value = {}

            explicit_ips = ['1.2.3.4', '5.6.7.8']
            await service.register_update_ips(explicit_ips)

            # Verify the function was called with explicit IPs only
            mock_register.assert_called_once()
            called_ips = mock_register.call_args[0][1]
            assert called_ips == explicit_ips

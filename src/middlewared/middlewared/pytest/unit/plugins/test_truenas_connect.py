import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from middlewared.service import ValidationErrors
from middlewared.plugins.truenas_connect.update import TrueNASConnectService
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
        old_config = {'enabled': False, 'ips': [], 'interfaces': [], 'status': Status.DISABLED.name}
        data = {'enabled': True, 'ips': [], 'interfaces': []}

        with pytest.raises(ValidationErrors) as exc_info:
            await tnc_service.validate_data(old_config, data)

        assert 'At least one IP or interface must be provided' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_data_interface_exists(self, tnc_service, mock_interfaces):
        """Test validation of interface existence."""
        tnc_service.middleware.call = AsyncMock(return_value=mock_interfaces)

        old_config = {'enabled': False, 'ips': [], 'interfaces': [], 'status': Status.DISABLED.name}
        data = {'enabled': True, 'ips': [], 'interfaces': ['ens3', 'invalid_interface']}

        with pytest.raises(ValidationErrors) as exc_info:
            await tnc_service.validate_data(old_config, data)

        assert 'Interface "invalid_interface" does not exist' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_data_interface_has_ip(self, tnc_service, mock_interfaces):
        """Test that selected interfaces must have at least one IP when no direct IPs provided."""
        tnc_service.middleware.call = AsyncMock(return_value=mock_interfaces)

        old_config = {'enabled': False, 'ips': [], 'interfaces': [], 'status': Status.DISABLED.name}
        data = {'enabled': True, 'ips': [], 'interfaces': ['ens5']}  # ens5 has no IPs

        with pytest.raises(ValidationErrors) as exc_info:
            await tnc_service.validate_data(old_config, data)

        assert 'Selected interfaces must have at least one IP address configured' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_data_interface_with_direct_ips(self, tnc_service, mock_interfaces):
        """Test that interface without IPs is allowed if direct IPs are provided."""
        tnc_service.middleware.call = AsyncMock(return_value=mock_interfaces)

        old_config = {'enabled': False, 'ips': [], 'interfaces': [], 'status': Status.DISABLED.name}
        data = {'enabled': True, 'ips': ['192.168.1.100'], 'interfaces': ['ens5']}  # ens5 has no IPs

        # Should not raise any errors
        await tnc_service.validate_data(old_config, data)

    @pytest.mark.asyncio
    async def test_validate_data_status_restriction(self, tnc_service, mock_interfaces):
        """Test that IPs/interfaces cannot be changed in certain states."""
        tnc_service.middleware.call = AsyncMock(return_value=mock_interfaces)

        old_config = {
            'enabled': True,
            'ips': ['192.168.1.10'],
            'interfaces': [],
            'status': Status.CERT_GENERATION_IN_PROGRESS.name,
            'account_service_base_url': 'https://example.com/',
            'leca_service_base_url': 'https://example.com/',
            'tnc_base_url': 'https://example.com/',
            'heartbeat_url': 'https://example.com/'
        }
        data = {
            'enabled': True,
            'ips': ['192.168.1.10'],
            'interfaces': ['ens3'],
            'account_service_base_url': 'https://example.com/',
            'leca_service_base_url': 'https://example.com/',
            'tnc_base_url': 'https://example.com/',
            'heartbeat_url': 'https://example.com/'
        }

        with pytest.raises(ValidationErrors) as exc_info:
            await tnc_service.validate_data(old_config, data)

        assert 'cannot be changed when TrueNAS Connect is in a state' in str(exc_info.value)


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
            'account_service_base_url': 'https://example.com/',
            'leca_service_base_url': 'https://example.com/',
            'tnc_base_url': 'https://example.com/',
            'heartbeat_url': 'https://example.com/'
        })

        tnc_service.middleware.call.side_effect = [
            # interface.query() call in validate_data
            mock_interfaces,
            # interface.query() call in do_update
            mock_interfaces,
            # alert.oneshot_delete calls
            None,
            None,
            # datastore.update() call
            None,
            # config() call for return value
            {
                'id': 1,
                'enabled': True,
                'ips': [],
                'interfaces': ['ens3', 'ens4'],
                'interfaces_ips': ['192.168.1.10', '2001:db8::1', '10.0.0.10'],
                'status': 'CLAIM_TOKEN_MISSING',
                'status_reason': 'Claim token is missing',
                'certificate': None,
                'account_service_base_url': 'https://example.com/',
                'leca_service_base_url': 'https://example.com/',
                'tnc_base_url': 'https://example.com/',
                'heartbeat_url': 'https://example.com/',
            },
        ]

        tnc_service.middleware.send_event = MagicMock()

        data = {
            'enabled': True,
            'ips': [],
            'interfaces': ['ens3', 'ens4']
        }

        await tnc_service.do_update(data)

        # Find the datastore.update call
        datastore_call = None
        for idx, call in enumerate(tnc_service.middleware.call.call_args_list):
            if call[0][0] == 'datastore.update':
                datastore_call = call
                break

        assert datastore_call is not None, (
            f"datastore.update not found in calls: "
            f"{[c[0][0] for c in tnc_service.middleware.call.call_args_list]}"
        )
        db_payload = datastore_call[0][3]

        # Check extracted IPs (should not include link-local IPv6)
        assert set(db_payload['interfaces_ips']) == {'192.168.1.10', '2001:db8::1', '10.0.0.10'}
        assert db_payload['interfaces'] == ['ens3', 'ens4']

    @pytest.mark.asyncio
    async def test_do_update_filters_link_local_ipv6(self, tnc_service):
        """Test that do_update filters out link-local IPv6 addresses."""
        mock_interfaces_with_link_local = [
            {
                'id': 'ens6',
                'state': {
                    'aliases': [
                        {'type': 'INET', 'address': '192.168.2.10'},
                        {'type': 'INET6', 'address': 'fe80::1234:5678:90ab:cdef'},
                        {'type': 'INET6', 'address': '2001:db8::2'},
                    ]
                }
            }
        ]

        tnc_service.middleware.call = AsyncMock()

        # Mock the config method
        tnc_service.config = AsyncMock(return_value={
            'id': 1,
            'enabled': False,
            'ips': [],
            'interfaces': [],
            'status': Status.DISABLED.name,
            'interfaces_ips': [],
            'account_service_base_url': 'https://example.com/',
            'leca_service_base_url': 'https://example.com/',
            'tnc_base_url': 'https://example.com/',
            'heartbeat_url': 'https://example.com/'
        })

        tnc_service.middleware.call.side_effect = [
            # interface.query() call in validate_data
            mock_interfaces_with_link_local,
            # interface.query() call in do_update
            mock_interfaces_with_link_local,
            # alert.oneshot_delete calls
            None,
            None,
            # datastore.update() call
            None,
            # config() call for return value
            {
                'id': 1,
                'enabled': True,
                'ips': [],
                'interfaces': ['ens6'],
                'interfaces_ips': ['192.168.2.10', '2001:db8::2'],
                'status': 'CLAIM_TOKEN_MISSING',
                'status_reason': 'Claim token is missing',
                'certificate': None,
                'account_service_base_url': 'https://example.com/',
                'leca_service_base_url': 'https://example.com/',
                'tnc_base_url': 'https://example.com/',
                'heartbeat_url': 'https://example.com/',
            },
        ]

        tnc_service.middleware.send_event = MagicMock()

        data = {
            'enabled': True,
            'ips': [],
            'interfaces': ['ens6']
        }

        await tnc_service.do_update(data)

        # Find the datastore.update call
        datastore_call = None
        for idx, call in enumerate(tnc_service.middleware.call.call_args_list):
            if call[0][0] == 'datastore.update':
                datastore_call = call
                break

        assert datastore_call is not None, (
            f"datastore.update not found in calls: "
            f"{[c[0][0] for c in tnc_service.middleware.call.call_args_list]}"
        )
        db_payload = datastore_call[0][3]

        # Check that link-local IPv6 was filtered out
        assert set(db_payload['interfaces_ips']) == {'192.168.2.10', '2001:db8::2'}
        assert 'fe80::1234:5678:90ab:cdef' not in db_payload['interfaces_ips']

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
            'account_service_base_url': 'https://example.com/',
            'leca_service_base_url': 'https://example.com/',
            'tnc_base_url': 'https://example.com/',
            'heartbeat_url': 'https://example.com/'
        })

        tnc_service.middleware.call.side_effect = [
            # interface.query() call in validate_data
            mock_interfaces,
            # interface.query() call in do_update
            mock_interfaces,
            # hostname.register_update_ips() call
            {'error': None},
            # datastore.update() call
            None,
        ]

        tnc_service.middleware.send_event = MagicMock()

        data = {
            'enabled': True,
            'ips': ['192.168.1.100'],
            'interfaces': ['ens4']
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

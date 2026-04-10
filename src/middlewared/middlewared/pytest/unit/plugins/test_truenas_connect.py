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
    async def test_validate_passes_with_effective_ips(self, tnc_service):
        """Validation passes when effective IPs are available."""
        async def mock_call(method, *args, **kwargs):
            if method == 'system.is_ha_capable':
                return False
            elif method == 'system.general.config':
                return {'ui_address': ['192.168.1.10'], 'ui_v6address': ['::']}
            elif method == 'interface.ip_in_use':
                return [{'address': '2001:db8::1'}]
            raise ValueError(f'Unexpected: {method}')

        tnc_service.middleware.call = AsyncMock(side_effect=mock_call)
        # Should not raise
        await tnc_service.validate_data({'enabled': True})

    @pytest.mark.asyncio
    async def test_validate_skips_when_disabled(self, tnc_service):
        """No IP validation when TNC is being disabled."""
        tnc_service.middleware.call = AsyncMock()
        # Should not raise regardless of IP state
        await tnc_service.validate_data({'enabled': False})


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

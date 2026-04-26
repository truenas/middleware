import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from middlewared.api.current import TrueNASConnectEntry
from middlewared.plugins.truenas_connect.config import TrueNASConnectConfigServicePart
from middlewared.plugins.truenas_connect.hostname import TNCHostnameService
from middlewared.plugins.truenas_connect.utils import TNC_IPS_CACHE_KEY
from middlewared.service import ValidationErrors


def make_tnc_entry(**overrides: Any) -> TrueNASConnectEntry:
    """Build a fully-populated TrueNASConnectEntry for tests, allowing per-field overrides."""
    defaults: dict[str, Any] = dict(
        id=1,
        enabled=True,
        registration_details={},
        status='CONFIGURED',
        status_reason='Configured',
        certificate=None,
        account_service_base_url='https://account.example/',
        leca_service_base_url='https://leca.example/',
        tnc_base_url='https://tnc.example/',
        heartbeat_url='https://hb.example/',
        tier=None,
        last_heartbeat_failure_datetime=None,
    )
    return TrueNASConnectEntry(**(defaults | overrides))


@pytest.fixture
def mock_context():
    """Create a mock ServiceContext-shaped object suitable for plain-function helpers."""
    ctx = MagicMock()
    ctx.middleware = MagicMock()
    ctx.middleware.call = AsyncMock()
    ctx.call2 = AsyncMock()
    return ctx


class TestTNCGetEffectiveIps:
    """Test get_effective_ips logic that derives IPs from system.general.config.

    get_effective_ips is now a plain function in internal.py — tests invoke it directly
    with a mocked ServiceContext.
    """

    @pytest.mark.asyncio
    async def test_wildcard_ipv4(self, mock_context):
        """When ui_address is 0.0.0.0, resolve to all IPv4 addresses via ip_in_use."""
        from middlewared.plugins.truenas_connect.internal import get_effective_ips

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

        mock_context.middleware.call = AsyncMock(side_effect=mock_call)
        result = await get_effective_ips(mock_context)
        assert set(result) == {'192.168.1.10', '10.0.0.10', '2001:db8::1'}

    @pytest.mark.asyncio
    async def test_wildcard_ipv6(self, mock_context):
        """When ui_v6address is ::, resolve to all non-link-local IPv6 addresses."""
        from middlewared.plugins.truenas_connect.internal import get_effective_ips

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

        mock_context.middleware.call = AsyncMock(side_effect=mock_call)
        result = await get_effective_ips(mock_context)
        assert set(result) == {'192.168.1.10', '2001:db8::1', '2001:db8::2'}

    @pytest.mark.asyncio
    async def test_both_wildcards(self, mock_context):
        """When both ui_address and ui_v6address are wildcards, resolve both families."""
        from middlewared.plugins.truenas_connect.internal import get_effective_ips

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

        mock_context.middleware.call = AsyncMock(side_effect=mock_call)
        result = await get_effective_ips(mock_context)
        assert set(result) == {'192.168.1.10', '2001:db8::1'}
        assert call_count['ipv4'] == 1
        assert call_count['ipv6'] == 1

    @pytest.mark.asyncio
    async def test_specific_ips(self, mock_context):
        """When specific IPs are given, return them directly without ip_in_use lookups."""
        from middlewared.plugins.truenas_connect.internal import get_effective_ips

        async def mock_call(method, *args, **kwargs):
            if method == 'system.general.config':
                return {'ui_address': ['192.168.1.10'], 'ui_v6address': ['2001:db8::1']}
            raise ValueError(f'Unexpected: {method}')

        mock_context.middleware.call = AsyncMock(side_effect=mock_call)
        result = await get_effective_ips(mock_context)
        assert result == ['192.168.1.10', '2001:db8::1']

    @pytest.mark.asyncio
    async def test_mixed_wildcard_v4_specific_v6(self, mock_context):
        """Mixing wildcard IPv4 and specific IPv6 should still resolve correctly."""
        from middlewared.plugins.truenas_connect.internal import get_effective_ips

        async def mock_call(method, *args, **kwargs):
            if method == 'system.general.config':
                return {'ui_address': ['0.0.0.0'], 'ui_v6address': ['2001:db8::1']}
            elif method == 'interface.ip_in_use':
                opts = args[0]
                assert opts['ipv4'] is True
                assert opts['ipv6'] is False
                return [{'address': '10.0.0.5'}, {'address': '172.16.0.1'}]
            raise ValueError(f'Unexpected: {method}')

        mock_context.middleware.call = AsyncMock(side_effect=mock_call)
        result = await get_effective_ips(mock_context)
        assert set(result) == {'10.0.0.5', '172.16.0.1', '2001:db8::1'}

    @pytest.mark.asyncio
    async def test_wildcard_resolves_to_empty(self, mock_context):
        """When wildcard resolves to no IPs, the result is empty."""
        from middlewared.plugins.truenas_connect.internal import get_effective_ips

        async def mock_call(method, *args, **kwargs):
            if method == 'system.general.config':
                return {'ui_address': ['0.0.0.0'], 'ui_v6address': ['2001:db8::1']}
            elif method == 'interface.ip_in_use':
                return []
            raise ValueError(f'Unexpected: {method}')

        mock_context.middleware.call = AsyncMock(side_effect=mock_call)
        result = await get_effective_ips(mock_context)
        assert result == ['2001:db8::1']


class TestTNCValidation:
    """Test TNC config validation logic.

    Validation lives on TrueNASConnectConfigServicePart._validate after the typesafe
    conversion. Tests build a TrueNASConnectEntry and call _validate directly.
    """

    @pytest.fixture
    def part(self):
        ctx = MagicMock()
        ctx.middleware = MagicMock()
        ctx.middleware.call = AsyncMock()
        ctx.logger = MagicMock()
        return TrueNASConnectConfigServicePart(ctx)

    @pytest.mark.asyncio
    async def test_validate_ha_requires_vips(self, part):
        """On HA systems, enabling TNC requires VIPs to exist."""
        async def mock_call(method, *args, **kwargs):
            if method == 'system.is_ha_capable':
                return True
            elif method == 'interface.query':
                return [{'failover_virtual_aliases': []}]
            raise ValueError(f'Unexpected: {method}')

        part.middleware.call = AsyncMock(side_effect=mock_call)

        with pytest.raises(ValidationErrors) as exc_info:
            await part._validate(make_tnc_entry(enabled=True))

        assert 'HA systems must be in a healthy state' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_non_ha_requires_effective_ips(self, part):
        """On non-HA systems, enabling TNC requires at least one effective IP."""
        async def mock_call(method, *args, **kwargs):
            if method == 'system.is_ha_capable':
                return False
            elif method == 'system.general.config':
                return {'ui_address': ['0.0.0.0'], 'ui_v6address': ['::']}
            elif method == 'interface.ip_in_use':
                return []
            raise ValueError(f'Unexpected: {method}')

        part.middleware.call = AsyncMock(side_effect=mock_call)

        with pytest.raises(ValidationErrors) as exc_info:
            await part._validate(make_tnc_entry(enabled=True))

        assert 'at least one IP address' in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_passes_with_effective_ips(self, part):
        """Validation passes when effective IPs are available."""
        async def mock_call(method, *args, **kwargs):
            if method == 'system.is_ha_capable':
                return False
            elif method == 'system.general.config':
                return {'ui_address': ['192.168.1.10'], 'ui_v6address': ['::']}
            elif method == 'interface.ip_in_use':
                return [{'address': '2001:db8::1'}]
            raise ValueError(f'Unexpected: {method}')

        part.middleware.call = AsyncMock(side_effect=mock_call)
        # Should not raise
        await part._validate(make_tnc_entry(enabled=True))

    @pytest.mark.asyncio
    async def test_validate_skips_when_disabled(self, part):
        """No IP validation when TNC is being disabled."""
        part.middleware.call = AsyncMock()
        # Should not raise regardless of IP state
        await part._validate(make_tnc_entry(enabled=False))


class TestTNCHostnameService:
    """Test hostname service updates.

    After conversion, the cross-sub-service helpers (config_internal, get_effective_ips,
    ha_vips) are plain functions imported into hostname.py. Tests patch them at the
    hostname module path so the in-process call resolves to the mock.
    `tn_connect.config` is reached via self.call2, so we mock `service.middleware.call2`.
    """

    @pytest.mark.asyncio
    async def test_register_update_ips_uses_effective_ips(self):
        """register_update_ips calls get_effective_ips when no IPs provided."""
        service = TNCHostnameService(MagicMock())

        async def mock_middleware_call(method, *args, **kwargs):
            if method == 'system.is_ha_capable':
                return False
            return None

        service.middleware.call = AsyncMock(side_effect=mock_middleware_call)

        with patch(
            'middlewared.plugins.truenas_connect.hostname.config_internal',
            new_callable=AsyncMock, return_value={'jwt_token': 'test_token'},
        ), patch(
            'middlewared.plugins.truenas_connect.hostname.get_effective_ips',
            new_callable=AsyncMock, return_value=['192.168.1.10', '2001:db8::1'],
        ), patch(
            'middlewared.plugins.truenas_connect.hostname.register_update_ips',
            new_callable=AsyncMock,
        ) as mock_register:
            mock_register.return_value = {}
            await service.register_update_ips()

            mock_register.assert_called_once()
            called_ips = mock_register.call_args[0][1]
            assert set(called_ips) == {'192.168.1.10', '2001:db8::1'}

    @pytest.mark.asyncio
    async def test_register_update_ips_with_explicit_ips(self):
        """register_update_ips uses provided IPs when specified."""
        service = TNCHostnameService(MagicMock())

        async def mock_middleware_call(method, *args, **kwargs):
            if method == 'system.is_ha_capable':
                return False
            return None

        service.middleware.call = AsyncMock(side_effect=mock_middleware_call)

        with patch(
            'middlewared.plugins.truenas_connect.hostname.config_internal',
            new_callable=AsyncMock, return_value={'jwt_token': 'test_token'},
        ), patch(
            'middlewared.plugins.truenas_connect.hostname.register_update_ips',
            new_callable=AsyncMock,
        ) as mock_register:
            mock_register.return_value = {}
            explicit_ips = ['1.2.3.4', '5.6.7.8']
            await service.register_update_ips(explicit_ips)

            mock_register.assert_called_once()
            called_ips = mock_register.call_args[0][1]
            assert called_ips == explicit_ips

    @pytest.mark.asyncio
    async def test_register_update_ips_ha_prepends_vips(self):
        """HA systems prepend VIPs to the IP list."""
        service = TNCHostnameService(MagicMock())

        async def mock_middleware_call(method, *args, **kwargs):
            if method == 'system.is_ha_capable':
                return True
            return None

        service.middleware.call = AsyncMock(side_effect=mock_middleware_call)

        with patch(
            'middlewared.plugins.truenas_connect.hostname.config_internal',
            new_callable=AsyncMock, return_value={'jwt_token': 'test_token'},
        ), patch(
            'middlewared.plugins.truenas_connect.hostname.get_effective_ips',
            new_callable=AsyncMock, return_value=['192.168.1.10'],
        ), patch(
            'middlewared.plugins.truenas_connect.hostname.ha_vips',
            new_callable=AsyncMock, return_value=['10.0.0.100'],
        ), patch(
            'middlewared.plugins.truenas_connect.hostname.register_update_ips',
            new_callable=AsyncMock,
        ) as mock_register:
            mock_register.return_value = {}
            await service.register_update_ips()

            called_ips = mock_register.call_args[0][1]
            # VIPs should be first
            assert called_ips == ['10.0.0.100', '192.168.1.10']

    @pytest.mark.asyncio
    async def test_sync_ips_skips_when_no_wildcards(self):
        """Network events are ignored when system.general has only specific IPs."""
        service = TNCHostnameService(MagicMock())
        service.config = AsyncMock()
        service.middleware.call2 = AsyncMock(return_value=make_tnc_entry(status='CONFIGURED'))

        async def mock_middleware_call(method, *args, **kwargs):
            if method == 'failover.is_single_master_node':
                return True
            elif method == 'system.general.config':
                return {'ui_address': ['192.168.1.10'], 'ui_v6address': ['2001:db8::1']}
            raise ValueError(f'Unexpected: {method}')

        service.middleware.call = AsyncMock(side_effect=mock_middleware_call)

        with patch(
            'middlewared.plugins.truenas_connect.hostname.get_effective_ips',
            new_callable=AsyncMock,
            side_effect=AssertionError('get_effective_ips should not be called'),
        ):
            # With event_details, should skip when no wildcards
            await service.sync_ips(event_details={'type': 'ipaddress.change', 'iface': 'ens3'})

    @pytest.mark.asyncio
    async def test_sync_ips_proceeds_with_wildcards(self):
        """Network events trigger sync when wildcards are configured."""
        service = TNCHostnameService(MagicMock())
        service.config = AsyncMock(return_value={})
        service.register_update_ips = AsyncMock(return_value={'error': None})
        service.middleware.call2 = AsyncMock(return_value=make_tnc_entry(status='CONFIGURED'))
        service.middleware.call_hook = AsyncMock()

        async def mock_middleware_call(method, *args, **kwargs):
            if method == 'failover.is_single_master_node':
                return True
            elif method == 'system.general.config':
                return {'ui_address': ['0.0.0.0'], 'ui_v6address': ['::']}
            elif method == 'cache.get':
                raise KeyError('miss')
            elif method == 'cache.put':
                return None
            raise ValueError(f'Unexpected: {method}')

        service.middleware.call = AsyncMock(side_effect=mock_middleware_call)

        with patch(
            'middlewared.plugins.truenas_connect.hostname.get_effective_ips',
            new_callable=AsyncMock, return_value=['192.168.1.10', '2001:db8::1'],
        ):
            await service.sync_ips(event_details={'type': 'ipaddress.change', 'iface': 'ens3'})

        service.register_update_ips.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_ips_skips_when_cached(self):
        """Sync is skipped when cached IPs match current IPs."""
        service = TNCHostnameService(MagicMock())
        service.config = AsyncMock()
        service.register_update_ips = AsyncMock(
            side_effect=AssertionError('Should not sync when cached IPs match'),
        )
        service.middleware.call2 = AsyncMock(return_value=make_tnc_entry(status='CONFIGURED'))

        async def mock_middleware_call(method, *args, **kwargs):
            if method == 'failover.is_single_master_node':
                return True
            elif method == 'cache.get':
                return ['192.168.1.10']
            return None

        service.middleware.call = AsyncMock(side_effect=mock_middleware_call)

        with patch(
            'middlewared.plugins.truenas_connect.hostname.get_effective_ips',
            new_callable=AsyncMock, return_value=['192.168.1.10'],
        ):
            # No event_details = no wildcard check, goes straight to resolve + cache compare
            await service.sync_ips()

    @pytest.mark.asyncio
    async def test_sync_ips_empty_effective_ips_skips_http(self):
        """sync_ips skips HTTP call when effective IPs are empty."""
        service = TNCHostnameService(MagicMock())
        service.config = AsyncMock()
        service.register_update_ips = AsyncMock(
            side_effect=AssertionError('Should not call register when IPs are empty'),
        )
        service.middleware.call_hook = AsyncMock()
        service.middleware.call2 = AsyncMock(return_value=make_tnc_entry(status='CONFIGURED'))

        cache_put_args = None

        async def mock_middleware_call(method, *args, **kwargs):
            nonlocal cache_put_args
            if method == 'failover.is_single_master_node':
                return True
            elif method == 'cache.get':
                raise KeyError('miss')
            elif method == 'cache.put':
                cache_put_args = args
                return None
            return None

        service.middleware.call = AsyncMock(side_effect=mock_middleware_call)

        with patch(
            'middlewared.plugins.truenas_connect.hostname.get_effective_ips',
            new_callable=AsyncMock, return_value=[],
        ):
            await service.sync_ips()

        assert cache_put_args is not None
        assert cache_put_args[0] == TNC_IPS_CACHE_KEY
        assert cache_put_args[1] == []
        service.middleware.call_hook.assert_not_called()

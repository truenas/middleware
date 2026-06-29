from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from truenas_connect_utils.status import Status

from middlewared.api.current import TrueNASConnectEntry
from middlewared.plugins.truenas_connect.config import TrueNASConnectConfigServicePart
from middlewared.plugins.truenas_connect.hostname import TNCHostnameService
from middlewared.plugins.truenas_connect.utils import CONFIGURED_TNC_STATES, TNC_IPS_CACHE_KEY
from middlewared.service import CallError, ValidationErrors


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


class _HeartbeatLoopReached(Exception):
    """Raised by the patched heartbeat request so tests can prove the start guard was passed."""


async def _run_heartbeat(status: str, creds: dict | None):
    """Drive heartbeat_start_impl just past its start guard.

    Everything between the guard and the first request is patched out; the request itself raises
    _HeartbeatLoopReached. So: guard rejected -> CallError; guard passed -> _HeartbeatLoopReached.
    """
    from middlewared.plugins.truenas_connect import heartbeat as hb

    ctx = MagicMock()
    ctx.middleware = MagicMock()
    ctx.middleware.call = AsyncMock(return_value='25.10.0')

    with patch.object(hb, 'config_internal', new=AsyncMock(return_value={'status': status, 'id': 1})), \
            patch.object(hb, 'get_account_id_and_system_id', return_value=creds), \
            patch.object(hb, 'get_heartbeat_url', return_value='http://hb/{system_id}/{version}'), \
            patch.object(hb, 'parse_version_string', return_value='25.10'), \
            patch.object(hb, 'iterate_disks', return_value=[]), \
            patch.object(hb, '_build_payload', new=AsyncMock(return_value={})), \
            patch.object(hb, '_heartbeat_request', new=AsyncMock(side_effect=_HeartbeatLoopReached())):
        await hb.heartbeat_start_impl(ctx)


@pytest.mark.parametrize('status', [
    Status.CONFIGURED.name,
    Status.CERT_RENEWAL_IN_PROGRESS.name,
    Status.CERT_RENEWAL_SUCCESS.name,
    Status.CERT_RENEWAL_FAILURE.name,
])
@pytest.mark.asyncio
async def test_heartbeat_guard_passes_for_configured_states(status):
    """With valid creds, the heartbeat enters its loop (does not raise the guard CallError)."""
    creds = {'account_id': 'a', 'system_id': 's'}
    with pytest.raises(_HeartbeatLoopReached):
        await _run_heartbeat(status, creds)


@pytest.mark.asyncio
async def test_heartbeat_guard_rejects_unconfigured_state():
    """A non-configured status is rejected before any request is made."""
    creds = {'account_id': 'a', 'system_id': 's'}
    with pytest.raises(CallError):
        await _run_heartbeat(Status.REGISTRATION_FINALIZATION_FAILED.name, creds)


@pytest.mark.asyncio
async def test_heartbeat_guard_rejects_when_no_creds():
    """Missing creds is rejected even in a configured state."""
    with pytest.raises(CallError):
        await _run_heartbeat(Status.CONFIGURED.name, None)


def test_cert_renewal_failure_is_configured_state():
    assert Status.CERT_RENEWAL_FAILURE.name in CONFIGURED_TNC_STATES


@pytest.mark.asyncio
async def test_sync_ips_proceeds_in_renewal_failure():
    """sync_ips must not early-return when the box is in CERT_RENEWAL_FAILURE."""
    service = TNCHostnameService(MagicMock())
    service.config = AsyncMock(return_value={})
    service.register_update_ips = AsyncMock(return_value={'error': None})
    service.middleware.call2 = AsyncMock(
        return_value=make_tnc_entry(status=Status.CERT_RENEWAL_FAILURE.name),
    )
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
        new_callable=AsyncMock, return_value=['192.168.1.10'],
    ):
        await service.sync_ips(event_details={'type': 'ipaddress.change', 'iface': 'ens3'})

    service.register_update_ips.assert_called_once()


@pytest.mark.asyncio
async def test_handle_deregistration_unsets_and_deletes_cert():
    """A configured box with a cert is unset, an alert raised, and the cert deleted."""
    from middlewared.plugins.truenas_connect import internal

    ctx = MagicMock()
    ctx.middleware = MagicMock()
    ctx.middleware.call = AsyncMock()
    ctx.middleware.send_event = MagicMock()
    ctx.call2 = AsyncMock(return_value=MagicMock(model_dump=MagicMock(return_value={})))

    with patch.object(
        internal, 'config_internal',
        new=AsyncMock(return_value={'status': Status.CONFIGURED.name, 'certificate': 15, 'id': 1}),
    ), patch.object(internal, 'unset_registration_details', new=AsyncMock()) as unset, \
            patch.object(internal, 'delete_cert', new=AsyncMock()) as delete_cert:
        await internal.handle_tnc_deregistration(ctx)

    unset.assert_awaited_once_with(ctx, False)
    delete_cert.assert_awaited_once_with(ctx, 15)
    ctx.middleware.send_event.assert_called_once()
    # datastore.update flips enabled off and applies the unset payload
    update_call = next(
        c for c in ctx.middleware.call.call_args_list if c.args[0] == 'datastore.update'
    )
    payload = update_call.args[3]
    assert payload['enabled'] is False
    assert payload['certificate'] is None
    assert payload['status'] == Status.DISABLED.name


@pytest.mark.asyncio
async def test_handle_deregistration_noop_when_already_unset():
    """Idempotent: already DISABLED with no cert performs no datastore write or cert delete."""
    from middlewared.plugins.truenas_connect import internal

    ctx = MagicMock()
    ctx.middleware = MagicMock()
    ctx.middleware.call = AsyncMock()
    ctx.call2 = AsyncMock()

    with patch.object(
        internal, 'config_internal',
        new=AsyncMock(return_value={'status': Status.DISABLED.name, 'certificate': None, 'id': 1}),
    ), patch.object(internal, 'unset_registration_details', new=AsyncMock()) as unset, \
            patch.object(internal, 'delete_cert', new=AsyncMock()) as delete_cert:
        await internal.handle_tnc_deregistration(ctx)

    unset.assert_not_called()
    delete_cert.assert_not_called()
    ctx.middleware.call.assert_not_called()


def _make_acme_service(acme_cfg):
    """Build a TNCACMEService whose call_sync2 dispatches by service-shortcut identity.

    Returns (service, dereg_calls); dereg_calls records when handle_deregistration is invoked.
    """
    from middlewared.plugins.truenas_connect.acme import TNCACMEService

    service = TNCACMEService(MagicMock())
    service.middleware.call_sync2 = MagicMock(return_value=MagicMock(certificate='PEM'))
    dereg_calls = []

    def dispatch(target, *args, **kwargs):
        if target is service.s.tn_connect.config:
            return MagicMock(certificate=15)
        if target is service.s.tn_connect.acme.config:
            return acme_cfg
        if target is service.s.tn_connect.handle_deregistration:
            dereg_calls.append(True)
            return None
        raise AssertionError(f'unexpected call_sync2 target: {target}')

    service.call_sync2 = MagicMock(side_effect=dispatch)
    return service, dereg_calls


def test_check_renewal_401_routes_to_deregistration():
    service, dereg_calls = _make_acme_service(
        {'status_code': 401, 'error': "HTTP 401: 'Unauthorized'", 'acme_details': {}},
    )
    with patch('middlewared.plugins.truenas_connect.acme.get_cert_id', return_value='cid'):
        result = service.check_renewal_needed()
    assert result == (False, None)
    assert dereg_calls == [True]


def test_check_renewal_non_401_error_does_not_deregister():
    service, dereg_calls = _make_acme_service(
        {'status_code': 500, 'error': 'HTTP 500: boom', 'acme_details': {}},
    )
    with patch('middlewared.plugins.truenas_connect.acme.get_cert_id', return_value='cid'):
        result = service.check_renewal_needed()
    assert result == (False, None)
    assert dereg_calls == []


def test_check_renewal_error_without_status_code_does_not_deregister():
    """acme_config's early-return omits status_code; .get() must not raise or trigger dereg."""
    service, dereg_calls = _make_acme_service(
        {'error': 'TrueNAS Connect is not enabled or not configured properly', 'acme_details': {}},
    )
    with patch('middlewared.plugins.truenas_connect.acme.get_cert_id', return_value='cid'):
        result = service.check_renewal_needed()
    assert result == (False, None)
    assert dereg_calls == []


@pytest.mark.asyncio
async def test_state_check_failure_triggers_renew_and_heartbeat():
    from middlewared.plugins.truenas_connect import state as state_mod

    ctx = MagicMock()
    ctx.middleware = MagicMock()
    ctx.middleware.create_task = MagicMock()
    ctx.call2 = AsyncMock(return_value=make_tnc_entry(status=Status.CERT_RENEWAL_FAILURE.name))

    await state_mod.state_check_impl(ctx, restart_ui=False)

    # One task for renew_cert (recovery branch) + one for heartbeat_start (CONFIGURED_TNC_STATES).
    assert ctx.middleware.create_task.call_count == 2


# --- Heartbeat request payload --------------------------------------------------------------------

def _payload_ctx(license_info, fingerprint='FP', fingerprint_raises=False):
    """ctx whose middleware.call serves the methods _build_payload needs."""
    ctx = MagicMock()
    ctx.middleware = MagicMock()
    ctx.call2 = AsyncMock(return_value=[])  # app.query / vm.query / alert.list all return lists

    async def mock_call(method, *args, **kwargs):
        if method == 'reporting.realtime.stats':
            return {}
        if method == 'truenas.license.fingerprint':
            if fingerprint_raises:
                raise CallError('daemon down')
            return fingerprint
        if method == 'truenas.license.info':
            return license_info
        raise ValueError(f'Unexpected: {method}')

    ctx.middleware.call = AsyncMock(side_effect=mock_call)
    return ctx


@pytest.mark.asyncio
async def test_build_payload_reports_fingerprint_and_license_id():
    from middlewared.plugins.truenas_connect import heartbeat as hb
    ctx = _payload_ctx(license_info={'id': 'LIC-1'}, fingerprint='FP-XYZ')
    payload = await hb._build_payload(ctx, {})
    assert payload['fingerprint'] == 'FP-XYZ'
    assert payload['license_id'] == 'LIC-1'


@pytest.mark.asyncio
async def test_build_payload_license_id_null_when_unlicensed():
    from middlewared.plugins.truenas_connect import heartbeat as hb
    ctx = _payload_ctx(license_info=None)
    payload = await hb._build_payload(ctx, {})
    assert payload['license_id'] is None


@pytest.mark.asyncio
async def test_build_payload_fingerprint_failure_degrades_to_null():
    from middlewared.plugins.truenas_connect import heartbeat as hb
    ctx = _payload_ctx(license_info={'id': 'LIC-1'}, fingerprint_raises=True)
    payload = await hb._build_payload(ctx, {})
    assert payload['fingerprint'] is None
    assert payload['license_id'] == 'LIC-1'  # other fields still populated


# --- License install (dedup + always-install + never crash) ---------------------------------------

def _install_ctx(installed_raw, upload_raises=False):
    ctx = MagicMock()
    ctx.middleware = MagicMock()

    async def mock_call(method, *args, **kwargs):
        if method == 'system.license':
            return {'raw_license': installed_raw} if installed_raw is not None else None
        if method == 'truenas.license.upload':
            if upload_raises:
                raise CallError('bad license')
            return None
        raise ValueError(f'Unexpected: {method}')

    ctx.middleware.call = AsyncMock(side_effect=mock_call)
    return ctx


def _upload_calls(ctx):
    return [c for c in ctx.middleware.call.call_args_list if c.args[0] == 'truenas.license.upload']


@pytest.mark.asyncio
async def test_maybe_install_license_installs_when_different():
    from middlewared.plugins.truenas_connect import heartbeat as hb
    ctx = _install_ctx(installed_raw='OLD-PEM')
    await hb._maybe_install_license(ctx, 'NEW-PEM')
    calls = _upload_calls(ctx)
    assert len(calls) == 1
    assert calls[0].args[1] == 'NEW-PEM'


@pytest.mark.asyncio
async def test_maybe_install_license_installs_when_no_current():
    from middlewared.plugins.truenas_connect import heartbeat as hb
    ctx = _install_ctx(installed_raw=None)
    await hb._maybe_install_license(ctx, 'NEW-PEM')
    assert len(_upload_calls(ctx)) == 1


@pytest.mark.asyncio
async def test_maybe_install_license_skips_when_identical():
    from middlewared.plugins.truenas_connect import heartbeat as hb
    # Trailing whitespace differs but content matches -> dedup must skip.
    ctx = _install_ctx(installed_raw='SAME-PEM')
    await hb._maybe_install_license(ctx, '  SAME-PEM\n')
    assert _upload_calls(ctx) == []


@pytest.mark.asyncio
async def test_maybe_install_license_swallows_upload_error():
    from middlewared.plugins.truenas_connect import heartbeat as hb
    ctx = _install_ctx(installed_raw='OLD-PEM', upload_raises=True)
    # Must not raise -- a failed install cannot kill the heartbeat loop.
    await hb._maybe_install_license(ctx, 'NEW-PEM')
    assert len(_upload_calls(ctx)) == 1


# --- Token rotation persistence -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_persist_new_token_writes_and_updates_in_memory():
    from middlewared.plugins.truenas_connect import heartbeat as hb

    ctx = MagicMock()
    ctx.middleware = MagicMock()
    ctx.middleware.call = AsyncMock()
    tnc_config = {'id': 1, 'jwt_token': 'OLD'}
    decoded = {'account_id': 'a', 'system_id': 's'}

    with patch.object(hb, 'decode_and_validate_token', return_value=decoded):
        await hb._persist_new_token(ctx, tnc_config, 'NEW-TOKEN')

    update_call = next(c for c in ctx.middleware.call.call_args_list if c.args[0] == 'datastore.update')
    assert update_call.args[1] == 'truenas_connect'
    assert update_call.args[3] == {'jwt_token': 'NEW-TOKEN', 'registration_details': decoded}
    # In-memory config updated so the next request authenticates with the new token.
    assert tnc_config['jwt_token'] == 'NEW-TOKEN'
    assert tnc_config['registration_details'] == decoded


@pytest.mark.asyncio
async def test_persist_new_token_skips_invalid_token():
    from middlewared.plugins.truenas_connect import heartbeat as hb

    ctx = MagicMock()
    ctx.middleware = MagicMock()
    ctx.middleware.call = AsyncMock()
    tnc_config = {'id': 1, 'jwt_token': 'OLD'}

    with patch.object(hb, 'decode_and_validate_token', side_effect=ValueError('bad')):
        await hb._persist_new_token(ctx, tnc_config, 'BROKEN')

    ctx.middleware.call.assert_not_called()
    assert tnc_config['jwt_token'] == 'OLD'  # unchanged


# --- 2xx response dispatch ------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize('body, expect_token, expect_license', [
    # A token is persisted whenever new_token is present -- even with token_status='active', which is
    # the decoupling the reviewer asked for (rotation can be issued while the old token is active).
    ({'token_status': 'active', 'new_token': 'T'}, 'T', None),
    # A token under 'rotating' is likewise persisted.
    ({'token_status': 'rotating', 'new_token': 'T'}, 'T', None),
    # A PEM is installed whenever present, regardless of license_status.
    ({'license_status': 'pending', 'license': 'PEM'}, None, 'PEM'),
    ({'license_status': 'accepted', 'license': 'PEM'}, None, 'PEM'),
    # Both artifacts present -> both handled.
    ({'new_token': 'T', 'license': 'PEM'}, 'T', 'PEM'),
    # Empty fields / empty body -> nothing.
    ({'token_status': 'active', 'new_token': '', 'license_status': 'pending', 'license': ''}, None, None),
    ({}, None, None),
])
async def test_handle_heartbeat_response_dispatch(body, expect_token, expect_license):
    from middlewared.plugins.truenas_connect import heartbeat as hb

    ctx = MagicMock()
    tnc_config = {'id': 1}

    with patch.object(hb, '_persist_new_token', new=AsyncMock()) as persist, \
            patch.object(hb, '_maybe_install_license', new=AsyncMock()) as install:
        # 202 keeps the focus on field-driven routing without tripping the 205 fault check.
        await hb._handle_heartbeat_response(ctx, tnc_config, 202, body)

    if expect_token is None:
        persist.assert_not_called()
    else:
        persist.assert_awaited_once_with(ctx, tnc_config, expect_token)

    if expect_license is None:
        install.assert_not_called()
    else:
        install.assert_awaited_once_with(ctx, expect_license)


@pytest.mark.asyncio
async def test_handle_heartbeat_response_handles_token_and_license_together():
    """A single 205 may carry both a rotated token and a delivered license."""
    from middlewared.plugins.truenas_connect import heartbeat as hb

    ctx = MagicMock()
    tnc_config = {'id': 1}
    body = {'token_status': 'rotating', 'new_token': 'T', 'license_status': 'pending', 'license': 'PEM'}

    with patch.object(hb, '_persist_new_token', new=AsyncMock()) as persist, \
            patch.object(hb, '_maybe_install_license', new=AsyncMock()) as install:
        await hb._handle_heartbeat_response(ctx, tnc_config, 205, body)

    persist.assert_awaited_once_with(ctx, tnc_config, 'T')
    install.assert_awaited_once_with(ctx, 'PEM')


@pytest.mark.asyncio
async def test_handle_heartbeat_response_205_without_artifact_warns():
    """A 205 promising an artifact but carrying none is a TNC fault we must surface, not skip."""
    from middlewared.plugins.truenas_connect import heartbeat as hb

    ctx = MagicMock()
    body = {'token_status': 'active', 'license_status': 'pending', 'license': '', 'new_token': ''}

    with patch.object(hb, '_persist_new_token', new=AsyncMock()) as persist, \
            patch.object(hb, '_maybe_install_license', new=AsyncMock()) as install, \
            patch.object(hb.logger, 'warning') as warn:
        await hb._handle_heartbeat_response(ctx, {'id': 1}, 205, body)

    persist.assert_not_called()
    install.assert_not_called()
    assert any('no license or token' in str(c.args[0]) for c in warn.call_args_list)


@pytest.mark.asyncio
async def test_handle_heartbeat_response_202_pending_without_pem_is_quiet():
    """A 202 with pending-but-no-PEM is normal (signing in progress) and must not warn."""
    from middlewared.plugins.truenas_connect import heartbeat as hb

    ctx = MagicMock()
    body = {'token_status': 'active', 'license_status': 'pending', 'license': '', 'new_token': ''}

    with patch.object(hb, '_maybe_install_license', new=AsyncMock()) as install, \
            patch.object(hb.logger, 'warning') as warn:
        await hb._handle_heartbeat_response(ctx, {'id': 1}, 202, body)

    install.assert_not_called()
    warn.assert_not_called()

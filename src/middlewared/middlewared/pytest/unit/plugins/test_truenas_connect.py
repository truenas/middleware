import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from truenas_connect_utils.status import Status

from middlewared.service import CallError, ValidationErrors
from middlewared.plugins.truenas_connect.acme import TNCACMEService
from middlewared.plugins.truenas_connect.heartbeat import TNCHeartbeatService
from middlewared.plugins.truenas_connect.state import TrueNASConnectStateService
from middlewared.plugins.truenas_connect.update import TrueNASConnectService
from middlewared.plugins.truenas_connect.hostname import TNCHostnameService
from middlewared.plugins.truenas_connect.utils import CONFIGURED_TNC_STATES, TNC_IPS_CACHE_KEY


@pytest.fixture
def tnc_service():
    """Create a mock TrueNASConnectService instance."""
    service = TrueNASConnectService(MagicMock())
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


def test_cert_renewal_failure_is_configured_state():
    assert Status.CERT_RENEWAL_FAILURE.name in CONFIGURED_TNC_STATES


@pytest.mark.asyncio
async def test_handle_deregistration_unsets_and_deletes_cert():
    """A configured box with a cert is unset, an alert raised, and the cert deleted."""
    service = TrueNASConnectService(MagicMock())
    service.config_internal = AsyncMock(
        return_value={'status': Status.CONFIGURED.name, 'certificate': 15, 'id': 1},
    )
    service.config = AsyncMock(return_value={'id': 1})
    service.unset_registration_details = AsyncMock()
    service.delete_cert = AsyncMock()
    service.middleware.send_event = MagicMock()

    calls = []

    async def mock_call(method, *args, **kwargs):
        calls.append((method, args))
        return None

    service.middleware.call = AsyncMock(side_effect=mock_call)

    await service.handle_tnc_deregistration()

    service.unset_registration_details.assert_awaited_once_with(False)
    service.delete_cert.assert_awaited_once_with(15)
    service.middleware.send_event.assert_called_once()
    update_call = next(c for c in calls if c[0] == 'datastore.update')
    payload = update_call[1][2]
    assert payload['enabled'] is False
    assert payload['certificate'] is None
    assert payload['status'] == Status.DISABLED.name
    assert any(c[0] == 'alert.oneshot_create' and c[1][0] == 'TNCDisabledAutoUnconfigured' for c in calls)


@pytest.mark.asyncio
async def test_handle_deregistration_noop_when_already_unset():
    """Idempotent: already DISABLED with no cert performs no datastore write or cert delete."""
    service = TrueNASConnectService(MagicMock())
    service.config_internal = AsyncMock(
        return_value={'status': Status.DISABLED.name, 'certificate': None, 'id': 1},
    )
    service.unset_registration_details = AsyncMock()
    service.delete_cert = AsyncMock()
    service.middleware.call = AsyncMock()

    await service.handle_tnc_deregistration()

    service.unset_registration_details.assert_not_called()
    service.delete_cert.assert_not_called()
    service.middleware.call.assert_not_called()


def _make_acme_service(acme_cfg):
    """Build a TNCACMEService whose call_sync dispatches by method name.

    Returns (service, dereg_calls); dereg_calls records when handle_tnc_deregistration is invoked.
    """
    service = TNCACMEService(MagicMock())
    dereg_calls = []

    def call_sync(method, *args, **kwargs):
        if method == 'tn_connect.config':
            return {'certificate': 15}
        if method == 'certificate.get_instance':
            return {'certificate': 'PEM'}
        if method == 'tn_connect.acme.config':
            return acme_cfg
        if method == 'tn_connect.handle_tnc_deregistration':
            dereg_calls.append(True)
            return None
        raise AssertionError(f'unexpected call_sync: {method}')

    service.middleware.call_sync = MagicMock(side_effect=call_sync)
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
    """Booting in CERT_RENEWAL_FAILURE re-attempts renewal and starts the heartbeat."""
    service = TrueNASConnectStateService(MagicMock())
    service.middleware.create_task = MagicMock()

    async def mock_call(method, *args, **kwargs):
        if method == 'tn_connect.config':
            return {'status': Status.CERT_RENEWAL_FAILURE.name}
        return None

    service.middleware.call = AsyncMock(side_effect=mock_call)

    await service.check(restart_ui=False)

    # One task for renew_cert (recovery branch) + one for heartbeat.start (CONFIGURED_TNC_STATES).
    assert service.middleware.create_task.call_count == 2


class _HeartbeatLoopReached(Exception):
    """Raised by the patched heartbeat request so tests can prove the start guard was passed."""


async def _run_heartbeat_start(status: str, creds: dict | None):
    """Drive TNCHeartbeatService.start just past its guard.

    The request call is patched to raise _HeartbeatLoopReached: guard rejected -> CallError;
    guard passed -> _HeartbeatLoopReached.
    """
    from middlewared.plugins.truenas_connect import heartbeat as hb

    service = TNCHeartbeatService(MagicMock())
    service.payload = AsyncMock(return_value={})
    service.call = AsyncMock(side_effect=_HeartbeatLoopReached())

    async def mock_call(method, *args, **kwargs):
        if method == 'tn_connect.config_internal':
            return {'status': status, 'id': 1}
        if method == 'system.version_short':
            return '25.10'
        return None

    service.middleware.call = AsyncMock(side_effect=mock_call)

    with patch.object(hb, 'get_account_id_and_system_id', return_value=creds), \
            patch.object(hb, 'get_heartbeat_url', return_value='http://hb/{system_id}/{version}'), \
            patch.object(hb, 'parse_version_string', return_value='25.10'), \
            patch.object(hb, 'iterate_disks', return_value=[]):
        await service.start()


@pytest.mark.parametrize('status', [
    Status.CONFIGURED.name,
    Status.CERT_RENEWAL_IN_PROGRESS.name,
    Status.CERT_RENEWAL_SUCCESS.name,
    Status.CERT_RENEWAL_FAILURE.name,
])
@pytest.mark.asyncio
async def test_heartbeat_guard_passes_for_configured_states(status):
    """With valid creds, the heartbeat enters its loop (does not raise the guard CallError)."""
    with pytest.raises(_HeartbeatLoopReached):
        await _run_heartbeat_start(status, {'account_id': 'a', 'system_id': 's'})


@pytest.mark.asyncio
async def test_heartbeat_guard_rejects_unconfigured_state():
    """A non-configured status is rejected before any request is made."""
    with pytest.raises(CallError):
        await _run_heartbeat_start(Status.REGISTRATION_FINALIZATION_FAILED.name, {'account_id': 'a', 'system_id': 's'})


@pytest.mark.asyncio
async def test_heartbeat_guard_rejects_when_no_creds():
    """Missing creds is rejected even in a configured state."""
    with pytest.raises(CallError):
        await _run_heartbeat_start(Status.CONFIGURED.name, None)


# --- Heartbeat request payload --------------------------------------------------------------------

def _payload_service(license_info, fingerprint='FP', fingerprint_raises=False):
    """A TNCHeartbeatService whose middleware.call serves what payload() needs."""
    service = TNCHeartbeatService(MagicMock())

    async def mock_call(method, *args, **kwargs):
        if method == 'reporting.realtime.stats':
            return {}
        if method in ('app.query', 'vm.query', 'alert.list'):
            return []
        if method == 'truenas.license.fingerprint':
            if fingerprint_raises:
                raise CallError('daemon down')
            return fingerprint
        if method == 'truenas.license.info':
            return license_info
        raise ValueError(f'Unexpected: {method}')

    service.middleware.call = AsyncMock(side_effect=mock_call)
    return service


@pytest.mark.asyncio
async def test_payload_reports_fingerprint_and_license_id():
    service = _payload_service(license_info={'id': 'LIC-1'}, fingerprint='FP-XYZ')
    payload = await service.payload({})
    assert payload['fingerprint'] == 'FP-XYZ'
    assert payload['license_id'] == 'LIC-1'


@pytest.mark.asyncio
async def test_payload_license_id_null_when_unlicensed():
    service = _payload_service(license_info=None)
    payload = await service.payload({})
    assert payload['license_id'] is None


@pytest.mark.asyncio
async def test_payload_fingerprint_failure_degrades_to_null():
    service = _payload_service(license_info={'id': 'LIC-1'}, fingerprint_raises=True)
    payload = await service.payload({})
    assert payload['fingerprint'] is None
    assert payload['license_id'] == 'LIC-1'  # other fields still populated


# --- License install (dedup + always-install + never crash) ---------------------------------------

def _install_service(installed_raw, upload_raises=False):
    service = TNCHeartbeatService(MagicMock())

    async def mock_call(method, *args, **kwargs):
        if method == 'system.license':
            return {'raw_license': installed_raw} if installed_raw is not None else None
        if method == 'truenas.license.upload':
            if upload_raises:
                raise CallError('bad license')
            return None
        raise ValueError(f'Unexpected: {method}')

    service.middleware.call = AsyncMock(side_effect=mock_call)
    return service


def _upload_calls(service):
    return [c for c in service.middleware.call.call_args_list if c.args[0] == 'truenas.license.upload']


@pytest.mark.asyncio
async def test_maybe_install_license_installs_when_different():
    service = _install_service(installed_raw='OLD-PEM')
    await service.maybe_install_license('NEW-PEM')
    calls = _upload_calls(service)
    assert len(calls) == 1
    assert calls[0].args[1] == 'NEW-PEM'


@pytest.mark.asyncio
async def test_maybe_install_license_installs_when_no_current():
    service = _install_service(installed_raw=None)
    await service.maybe_install_license('NEW-PEM')
    assert len(_upload_calls(service)) == 1


@pytest.mark.asyncio
async def test_maybe_install_license_skips_when_identical():
    # Trailing whitespace differs but content matches -> dedup must skip.
    service = _install_service(installed_raw='SAME-PEM')
    await service.maybe_install_license('  SAME-PEM\n')
    assert _upload_calls(service) == []


@pytest.mark.asyncio
async def test_maybe_install_license_swallows_upload_error():
    service = _install_service(installed_raw='OLD-PEM', upload_raises=True)
    # Must not raise -- a failed install cannot kill the heartbeat loop.
    await service.maybe_install_license('NEW-PEM')
    assert len(_upload_calls(service)) == 1


# --- Token rotation persistence -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_persist_new_token_writes_and_updates_in_memory():
    from middlewared.plugins.truenas_connect import heartbeat as hb

    service = TNCHeartbeatService(MagicMock())
    service.middleware.call = AsyncMock()
    tnc_config = {'id': 1, 'jwt_token': 'OLD'}
    decoded = {'account_id': 'a', 'system_id': 's'}

    with patch.object(hb, 'decode_and_validate_token', return_value=decoded):
        await service.persist_new_token(tnc_config, 'NEW-TOKEN')

    update_call = next(
        c for c in service.middleware.call.call_args_list if c.args[0] == 'datastore.update'
    )
    assert update_call.args[1] == 'truenas_connect'
    assert update_call.args[3] == {'jwt_token': 'NEW-TOKEN', 'registration_details': decoded}
    # In-memory config updated so the next request authenticates with the new token.
    assert tnc_config['jwt_token'] == 'NEW-TOKEN'
    assert tnc_config['registration_details'] == decoded


@pytest.mark.asyncio
async def test_persist_new_token_skips_invalid_token():
    from middlewared.plugins.truenas_connect import heartbeat as hb

    service = TNCHeartbeatService(MagicMock())
    service.middleware.call = AsyncMock()
    tnc_config = {'id': 1, 'jwt_token': 'OLD'}

    with patch.object(hb, 'decode_and_validate_token', side_effect=ValueError('bad')):
        await service.persist_new_token(tnc_config, 'BROKEN')

    service.middleware.call.assert_not_called()
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
async def test_handle_response_dispatch(body, expect_token, expect_license):
    service = TNCHeartbeatService(MagicMock())
    tnc_config = {'id': 1}

    with patch.object(service, 'persist_new_token', new=AsyncMock()) as persist, \
            patch.object(service, 'maybe_install_license', new=AsyncMock()) as install:
        # 202 keeps the focus on field-driven routing without tripping the 205 fault check.
        await service.handle_response(tnc_config, 202, body)

    if expect_token is None:
        persist.assert_not_called()
    else:
        persist.assert_awaited_once_with(tnc_config, expect_token)

    if expect_license is None:
        install.assert_not_called()
    else:
        install.assert_awaited_once_with(expect_license)


@pytest.mark.asyncio
async def test_handle_response_205_without_artifact_warns():
    """A 205 promising an artifact but carrying none is a TNC fault we must surface, not skip."""
    from middlewared.plugins.truenas_connect import heartbeat as hb

    service = TNCHeartbeatService(MagicMock())
    body = {'token_status': 'active', 'license_status': 'pending', 'license': '', 'new_token': ''}

    with patch.object(service, 'persist_new_token', new=AsyncMock()) as persist, \
            patch.object(service, 'maybe_install_license', new=AsyncMock()) as install, \
            patch.object(hb.logger, 'warning') as warn:
        await service.handle_response({'id': 1}, 205, body)

    persist.assert_not_called()
    install.assert_not_called()
    assert any('no license or token' in str(c.args[0]) for c in warn.call_args_list)


@pytest.mark.asyncio
async def test_handle_response_202_pending_without_pem_is_quiet():
    """A 202 with pending-but-no-PEM is normal (signing in progress) and must not warn."""
    from middlewared.plugins.truenas_connect import heartbeat as hb

    service = TNCHeartbeatService(MagicMock())
    body = {'token_status': 'active', 'license_status': 'pending', 'license': '', 'new_token': ''}

    with patch.object(service, 'maybe_install_license', new=AsyncMock()) as install, \
            patch.object(hb.logger, 'warning') as warn:
        await service.handle_response({'id': 1}, 202, body)

    install.assert_not_called()
    warn.assert_not_called()

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from truenas_connect_utils.status import Status
from middlewared.plugins.service_.services.pseudo.misc import HttpService


@pytest.fixture
def mock_middleware():
    """Create a mock middleware instance."""
    middleware = MagicMock()
    middleware.call = AsyncMock()
    middleware.create_task = MagicMock(side_effect=lambda coro: asyncio.create_task(coro))
    middleware.logger = MagicMock()
    return middleware


@pytest.fixture
def http_service(mock_middleware):
    """Create an HttpService instance with mock middleware."""
    service = HttpService(mock_middleware)
    service.middleware = mock_middleware
    return service


class TestHTTPServiceTNCPortRegistration:
    """Test TrueNAS Connect port registration with retry logic."""

    @pytest.mark.asyncio
    async def test_port_change_tnc_configured_success_first_attempt(
        self, http_service, mock_middleware
    ):
        """Test successful port registration on first attempt when TNC is configured and port changed."""
        mock_middleware.call.return_value = None

        # Call retry method directly
        await http_service._register_port_with_retry(8443)

        # Verify registration was called exactly once with correct port
        mock_middleware.call.assert_called_once_with('tn_connect.hostname.register_system_config', 8443)
        # Verify no error was logged
        mock_middleware.logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_port_change_tnc_disabled_no_registration(
        self, http_service, mock_middleware
    ):
        """Test that port is not registered when TNC status is DISABLED."""
        registration_called = False

        async def mock_call(method, *args, **kwargs):
            nonlocal registration_called
            if method == 'system.general.https_port_changed':
                return (True, 8443)
            elif method == 'tn_connect.config':
                return {'status': Status.DISABLED.name}
            elif method == 'tn_connect.hostname.register_system_config':
                registration_called = True
                return None

        mock_middleware.call.side_effect = mock_call

        # Trigger registration
        await http_service._register_new_port()
        await asyncio.sleep(0.1)

        # Verify registration was NOT called
        assert not registration_called
        # Verify create_task was NOT called
        mock_middleware.create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_port_change_tnc_configured_fails_once_then_succeeds(
        self, http_service, mock_middleware
    ):
        """Test port registration succeeds after one failure."""
        call_count = 0

        async def mock_call(method, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Network timeout")

        mock_middleware.call.side_effect = mock_call

        # Call retry method directly
        await http_service._register_port_with_retry(8443)

        # Verify it was called twice (failed once, succeeded on retry)
        assert mock_middleware.call.call_count == 2
        # Verify both calls were with correct method and port
        assert mock_middleware.call.call_args_list[0][0] == ('tn_connect.hostname.register_system_config', 8443)
        assert mock_middleware.call.call_args_list[1][0] == ('tn_connect.hostname.register_system_config', 8443)
        # Verify no error was logged (since it eventually succeeded)
        mock_middleware.logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_port_change_tnc_configured_fails_all_three_attempts(
        self, http_service, mock_middleware
    ):
        """Test port registration failure is logged after 3 failed attempts."""
        mock_middleware.call.side_effect = Exception("Connection refused")

        # Call retry method directly
        await http_service._register_port_with_retry(8443)

        # Verify it was called 3 times (all failed)
        assert mock_middleware.call.call_count == 3
        # Verify all calls were with correct method and port
        for call_args in mock_middleware.call.call_args_list:
            assert call_args[0] == ('tn_connect.hostname.register_system_config', 8443)
        # Verify error was logged
        mock_middleware.logger.error.assert_called_once()
        error_msg = mock_middleware.logger.error.call_args[0][0]
        assert 'Failed to register port with TrueNAS Connect after 3 attempts' in error_msg

    @pytest.mark.asyncio
    async def test_port_not_changed_no_registration(
        self, http_service, mock_middleware
    ):
        """Test that port is not registered when port has not changed."""
        registration_called = False

        async def mock_call(method, *args, **kwargs):
            nonlocal registration_called
            if method == 'system.general.https_port_changed':
                return (False, 443)
            elif method == 'tn_connect.config':
                return {'status': Status.CONFIGURED.name}
            elif method == 'tn_connect.hostname.register_system_config':
                registration_called = True
                return None

        mock_middleware.call.side_effect = mock_call

        # Trigger registration
        await http_service._register_new_port()
        await asyncio.sleep(0.1)

        # Verify registration was NOT called
        assert not registration_called
        # Verify create_task was NOT called
        mock_middleware.create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_correct_port_value_7443_passed_to_registration(
        self, http_service, mock_middleware
    ):
        """Test that the correct port value (7443) is passed to the registration method."""
        mock_middleware.call.return_value = None

        # Call retry method directly with specific port
        await http_service._register_port_with_retry(7443)

        # Verify correct port was passed
        mock_middleware.call.assert_called_once_with('tn_connect.hostname.register_system_config', 7443)

    @pytest.mark.asyncio
    async def test_after_restart_calls_register_new_port(
        self, http_service, mock_middleware
    ):
        """Test that after_restart hook calls _register_new_port and creates background task."""
        async def mock_call(method, *args, **kwargs):
            if method == 'system.general.https_port_changed':
                return (True, 8443)
            elif method == 'tn_connect.config':
                return {'status': Status.CONFIGURED}

        mock_middleware.call.side_effect = mock_call

        # Call after_restart hook
        await http_service.after_restart()

        # Verify middleware.call was called for checking port change and TNC config
        assert mock_middleware.call.call_count == 2
        mock_middleware.call.assert_any_call('system.general.https_port_changed')
        mock_middleware.call.assert_any_call('tn_connect.config')
        # Verify create_task was called (background task created)
        mock_middleware.create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_after_reload_calls_register_new_port(
        self, http_service, mock_middleware
    ):
        """Test that after_reload hook calls _register_new_port and creates background task."""
        async def mock_call(method, *args, **kwargs):
            if method == 'system.general.https_port_changed':
                return (True, 8443)
            elif method == 'tn_connect.config':
                return {'status': Status.CONFIGURED}

        mock_middleware.call.side_effect = mock_call

        # Call after_reload hook
        await http_service.after_reload()

        # Verify middleware.call was called for checking port change and TNC config
        assert mock_middleware.call.call_count == 2
        mock_middleware.call.assert_any_call('system.general.https_port_changed')
        mock_middleware.call.assert_any_call('tn_connect.config')
        # Verify create_task was called (background task created)
        mock_middleware.create_task.assert_called_once()

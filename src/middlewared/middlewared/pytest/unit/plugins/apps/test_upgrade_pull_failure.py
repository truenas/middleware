from unittest.mock import MagicMock, Mock

import pytest

from middlewared.plugins.apps.upgrade import AppService
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import CallError

PULL_ERROR = "Failed 'pull' action for 'custom-app' app. Please check /var/log/app_lifecycle.log for more details"

SUCCESS_PROGRESS = (100, "App successfully upgraded and redeployed")


def app_entry(**overrides):
    """Stands in for a running custom app that has an image update pending."""
    return {
        "state": "RUNNING",
        "upgrade_available": True,
        "custom_app": True,
        "metadata": {"name": "custom-app"},
    } | overrides


def test_custom_app_upgrade_surfaces_pull_failure():
    """A failed pull has to fail the job rather than return the app."""
    middleware = Middleware()
    middleware["app.get_instance"] = Mock(return_value=app_entry())
    middleware["app.pull_images_internal"] = Mock(side_effect=CallError(PULL_ERROR))
    job = MagicMock()

    with pytest.raises(CallError, match="Failed 'pull' action"):
        AppService(middleware).upgrade_impl(job, "custom-app", {})

    # The job must not claim the upgrade finished.
    assert SUCCESS_PROGRESS not in [c.args for c in job.set_progress.call_args_list]


def test_custom_app_upgrade_returns_app_on_success():
    """A successful pull and redeploy still short circuits with the refreshed app."""
    middleware = Middleware()
    app = app_entry()
    middleware["app.get_instance"] = Mock(return_value=app)
    middleware["app.pull_images_internal"] = Mock()
    job = MagicMock()

    assert AppService(middleware).upgrade_impl(job, "custom-app", {}) is app
    job.set_progress.assert_called_with(*SUCCESS_PROGRESS)
    middleware.send_event.assert_called_once()

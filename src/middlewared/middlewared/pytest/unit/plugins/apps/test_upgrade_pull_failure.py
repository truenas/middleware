from unittest.mock import MagicMock, patch

import pytest

from middlewared.plugins.apps.upgrade import upgrade_impl
from middlewared.service import CallError

PULL_ERROR = "Failed 'pull' action for 'custom-app' app. Please check /var/log/app_lifecycle.log for more details"

SUCCESS_PROGRESS = (100, "App successfully upgraded and redeployed")


def app_entry(**overrides):
    """Stands in for a running custom app that has an image update pending."""
    app = MagicMock()
    app.state = "RUNNING"
    app.upgrade_available = True
    app.custom_app = True
    app.metadata = {"name": "custom-app"}
    for key, value in overrides.items():
        setattr(app, key, value)
    return app


@patch("middlewared.plugins.apps.upgrade.assert_app_usable", MagicMock())
@patch("middlewared.plugins.apps.upgrade.pull_images_internal")
def test_custom_app_upgrade_surfaces_pull_failure(pull_images_internal):
    """A failed pull has to fail the job rather than return the app."""
    pull_images_internal.side_effect = CallError(PULL_ERROR)
    context = MagicMock()
    context.call_sync2.return_value = app_entry()
    job = MagicMock()

    with pytest.raises(CallError, match="Failed 'pull' action"):
        upgrade_impl(context, job, "custom-app", MagicMock())

    # The job must not claim the upgrade finished.
    assert SUCCESS_PROGRESS not in [c.args for c in job.set_progress.call_args_list]


@patch("middlewared.plugins.apps.upgrade.assert_app_usable", MagicMock())
@patch("middlewared.plugins.apps.upgrade.pull_images_internal", MagicMock())
def test_custom_app_upgrade_returns_app_on_success():
    """A successful pull and redeploy still short circuits with the refreshed app."""
    context = MagicMock()
    app = app_entry()
    context.call_sync2.return_value = app
    job = MagicMock()

    assert upgrade_impl(context, job, "custom-app", MagicMock()) is app
    job.set_progress.assert_called_with(*SUCCESS_PROGRESS)
    context.middleware.send_event.assert_called_once()

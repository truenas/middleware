import contextlib

from middlewared.test.integration.utils import call

SECURE_HTTP_SERVER = {"ui_httpsredirect": True, "ui_httpsprotocols": ["TLSv1.2", "TLSv1.3"]}


@contextlib.contextmanager
def http_server_settings(settings, call_fn=call):
    """Temporarily apply `settings` to the HTTP server configuration.

    nginx is deliberately left alone (no `system.general.ui_restart`), so the settings
    only reach the database. Restarting nginx here would drop the test client's
    connection and, for an insecure configuration, could lock the test run out of the
    API entirely.
    """
    config = call_fn("system.general.config")
    original = {key: config[key] for key in settings}
    call_fn("system.general.update", settings)
    try:
        yield
    finally:
        call_fn("system.general.update", original)

import contextlib

from middlewared.test.integration.utils import call, ssh

SOURCE = "SyslogNg"


@contextlib.contextmanager
def syslog_ng_stopped():
    ssh("systemctl stop syslog-ng")
    try:
        yield
    finally:
        ssh("systemctl start syslog-ng")


def test_no_alert_while_syslog_ng_runs():
    assert call("alert.run_source", SOURCE) == []


def test_alert_when_syslog_ng_is_stopped():
    with syslog_ng_stopped():
        alerts = call("alert.run_source", SOURCE)

    assert len(alerts) == 1, alerts
    assert alerts[0]["klass"] == SOURCE, alerts
    assert alerts[0]["text"].startswith("The syslog-ng service is not running"), alerts

import pytest

from middlewared.test.integration.utils import call, ssh, mock
from time import sleep


@pytest.fixture(scope='function')
def setup_state(request):
    """
    Parametrize the test setup
    The hope was that both 'backend' and 'setup' one-shot tests would be similar, however
    the 'setup' test ended up requiring 'with mock'
    """
    path = '/audit'
    alert_key = request.param[0]
    if alert_key is not None:
        path += f"/{alert_key}.db"
    alert_class = request.param[1]
    restore_data = None
    try:
        # Remove any pre-existing alert cruft
        call('alert.oneshot_delete', alert_class, alert_key if alert_key is None else {'service': alert_key})

        alerts = call("alert.list")
        class_alerts = [alert for alert in alerts if alert['klass'] == alert_class]
        assert len(class_alerts) == 0, class_alerts
        match alert_class:
            case 'AuditBackendSetup':
                # A file in the dataset: set it immutable
                ssh(f'chattr +i {path}')
                lsattr = ssh(f'lsattr {path}')
                assert lsattr[4] == 'i', lsattr
                restore_data = path
            case 'AuditDatasetCleanup':
                # Directly tweak the zfs settings
                call(
                    "zfs.dataset.update",
                    "boot-pool/ROOT/24.10.0-MASTER-20240709-021413/audit",
                    {"properties": {"org.freenas:refquota_warning": {"parsed": "70"}}}
                )
            case _:
                pass
        yield request.param
    finally:
        match alert_class:
            case 'AuditBackendSetup':
                # Remove immutable flag from file
                assert restore_data != ""
                ssh(f'chattr -i {restore_data}')
                lsattr = ssh(f'lsattr {restore_data}')
                assert lsattr[4] == '-', lsattr
                # Restore backend file descriptors and dismiss alerts
                call('auditbackend.setup')
            case 'AuditSetup':
                # Dismiss alerts
                call('audit.setup')
            case _:
                pass
        # call('alert.oneshot_delete', alert_class, alert_key if alert_key is None else {'service': alert_key})
        sleep(1)
        alerts = call("alert.list")
        class_alerts = [alert for alert in alerts if alert['klass'] == alert_class]
        assert len(class_alerts) == 0, class_alerts


@pytest.mark.parametrize(
    'setup_state', [
        ['SMB', 'AuditBackendSetup', 'auditbackend.setup'],
    ],
    indirect=True
)
def test_audit_backend_alert(setup_state):
    db_path, alert_class, audit_method = setup_state
    call(audit_method)
    sleep(1)
    alerts = call("alert.list")
    class_alerts = [alert for alert in alerts if alert['klass'] == alert_class]
    assert len(class_alerts) > 0, class_alerts
    assert class_alerts[0]['klass'] == 'AuditBackendSetup', class_alerts
    assert class_alerts[0]['args']['service'] == db_path, class_alerts
    assert class_alerts[0]['formatted'].startswith("Audit service failed backend setup"), class_alerts


def test_audit_health_monitor_alert():
    with mock("auditbackend.query", """
        from middlewared.service import private
        @private
        async def mock(self, *args):
            raise CallError('TEST_SERVICE: connection to audit database is not initialized.')
    """):
        alert = call("alert.run_source", "AuditServiceHealth")[0]
        assert alert['source'] == 'AuditServiceHealth', f"Received source: {alert['source']}"
        assert alert['text'].startswith("Failed to perform audit query"), f"Received text: {alert['text']}"
        assert "connection to audit database is not initialized" in alert['args']['verrs'], f"Received args: {alert['args']}"

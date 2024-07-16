import pytest

from middlewared.test.integration.utils import call, ssh, mock
from time import sleep


def setup_test(alert_class, alert_key, path):
    restore_val = None
    match alert_class:
        case 'AuditBackendSetup':
            # A file in the dataset: set it immutable
            ssh(f'chattr +i {path}')
            lsattr = ssh(f'lsattr {path}')
            assert lsattr[4] == 'i', lsattr
            restore_val = path
        case 'AuditDatasetCleanup':
            # Directly tweak the zfs settings
            call(
                "zfs.dataset.update",
                "boot-pool/ROOT/24.10.0-MASTER-20240709-021413/audit",
                {"properties": {"org.freenas:refquota_warning": {"parsed": "70"}}}
            )
        case _:
            pass

    return restore_val


def restore_test(alert_key, restore_val=()):
    match alert_key:
        case 'SMB':
            # Remove immutable flag from file
            assert restore_val != ""
            ssh(f'chattr -i {restore_val}')
            lsattr = ssh(f'lsattr {restore_val}')
            assert lsattr[4] == '-', lsattr
        case _:
            pass


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
    restore_data = ()
    try:
        call('alert.oneshot_delete', alert_class, alert_key if alert_key is None else {'service': alert_key})

        alerts = call("alert.list")
        class_alerts = [alert for alert in alerts if alert['klass'] == alert_class]
        assert len(class_alerts) == 0, class_alerts
        restore_data = setup_test(alert_class, alert_key, path)
        yield request.param
    finally:
        restore_test(alert_key, restore_data)
        call('alert.oneshot_delete', alert_class, alert_key if alert_key is None else {'service': alert_key})
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


@pytest.mark.parametrize(
    'setup_state', [
        [None, 'AuditSetup', 'audit.setup']
    ],
    indirect=True
)
def test_audit_setup_alert(setup_state):
    with mock("audit.update_audit_dataset", """
        from middlewared.service import private
        @private
        async def mock(self, new):
            raise Exception()
    """):
        unused, alert_class, audit_method = setup_state
        call(audit_method)
        sleep(1)
        alerts = call("alert.list")
        class_alerts = [alert for alert in alerts if alert['klass'] == alert_class]
        assert len(class_alerts) > 0, class_alerts
        assert class_alerts[0]['klass'] == 'AuditSetup', class_alerts
        assert class_alerts[0]['formatted'].startswith("Audit service failed to complete setup"), class_alerts


def test_audit_health_monitor_alert():
    with mock("auditbackend.query", """
        from middlewared.service import private
        from middlewared.schema import accepts, Str, List, Dict
        @private
        @accepts(
            Str('db_name', required=True),
            List('query-filters'),
            Dict('query-options')
        )
        async def mock(self, db_name, filters, options):
            raise CallError('TEST_SERVICE: connection to audit database is not initialized.')
    """):
        alert = call("alert.run_source", "AuditServiceHealth")[0]
        assert alert['source'] == 'AuditServiceHealth', alert
        assert alert['text'].startswith("Failed to perform audit query"), alert
        assert "connection to audit database is not initialized" in alert['args']['verrs'], alert

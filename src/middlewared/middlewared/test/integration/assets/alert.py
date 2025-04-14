from middlewared.test.integration.utils import call


class AlertMixin:
    def assert_alert_count(self, count):
        alerts = [alert for alert in call('alert.list') if alert['klass'] == self.ALERT_CLASS_NAME]
        assert len(alerts) == count, alerts

    def clear_alert(self):
        call('alert.oneshot_delete', self.ALERT_CLASS_NAME)
        self.assert_alert_count(0)

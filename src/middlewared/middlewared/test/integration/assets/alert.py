from time import sleep

from middlewared.test.integration.utils import call


class AlertMixin:
    def alert_count(self):
        return len([alert for alert in call('alert.list') if alert['klass'] == self.ALERT_CLASS_NAME])

    def assert_alert_count(self, count, retries=5):
        # Give a few seconds for the alerts to update
        for i in range(retries):
            if count == self.alert_count():
                return
            sleep(1)
        assert self.alert_count() == count

    def clear_alert(self):
        call('alert.oneshot_delete', self.ALERT_CLASS_NAME)
        self.assert_alert_count(0)

from django.utils.translation import ugettext as _

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert


class TrainAlert(BaseAlert):

    def run(self):
        return [Alert(
            Alert.WARN, _(
                'The 9.3-STABLE Train is now in Maintenance Mode. No new '
                'features or non-essential changes will be made. Please '
                'switch to the 9.10-STABLE train for active support.'
            )
        )]


alertPlugins.register(TrainAlert)

from django.utils.translation import ugettext as _

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from freenasOS import Configuration


class TrainAlert(BaseAlert):

    def run(self):
        conf = Configuration.Configuration()
        if conf.CurrentTrain() == 'FreeNAS-9.10-Nightlies':
            return [Alert(
                Alert.WARN, _(
                    'The 9.10-Nightlies Train is now abandoned. Please '
                    'switch to the 11-Nightlies train for active support.'
                )
            )]


alertPlugins.register(TrainAlert)

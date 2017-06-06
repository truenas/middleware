import os
import sys

from middlewared.schema import accepts
from middlewared.service import Service

# FIXME: temporary imports while license methods are still in django
if '/usr/local/www' not in sys.path:
    sys.path.append('/usr/local/www')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')
import django
django.setup()
from freenasUI.failover.detect import ha_hardware, ha_node
from freenasUI.support.utils import get_license


class FailoverService(Service):

    class Config:
        private = True

    @accepts()
    def licensed(self):
        """
        Checks whether this instance is licensed as a HA unit.
        """
        license, error = get_license()
        if license is None or not license.system_serial_ha:
            return False
        return True

    @accepts()
    def hardware(self):
        """
        Gets the hardware type of HA.

          ECHOSTREAM
          AIC
          PUMA
          SBB
          ULTIMATE
          MANUAL
        """
        return ha_hardware()

    @accepts()
    def node(self):
        """
        Gets the node identification.
          A - First node
          B - Seconde Node
          MANUAL - could not be identified, its in manual mode
        """
        node = ha_node()
        if node is None:
            return 'MANUAL'
        return node


def ha_permission(app):
    remote_addr = app.ws.environ['REMOTE_ADDR']
    remote_port = app.ws.environ['REMOTE_PORT']

    if remote_port <= 1024 and remote_addr in (
        '169.254.10.1',
        '169.254.10.2',
        '169.254.10.20',
        '169.254.10.80',
    ):
        app.authenticated = True


def setup(middleware):
    middleware.register_hook('core.on_connect', ha_permission, sync=True)

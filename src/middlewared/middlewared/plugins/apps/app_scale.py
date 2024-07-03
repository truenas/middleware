from middlewared.schema import accepts, Str, returns
from middlewared.service import Service

from .compose_utils import compose_action


class AppService(Service):

    class Config:
        namespace = 'app'
        cli_namespace = 'app'

    @accepts(Str('app_name'))
    @returns()
    def stop(self, app_name):
        """
        Stop `app_name` app.
        """
        app_config = self.middleware.call_sync('app.get_instance', app_name)
        compose_action(app_name, app_config['version'], 'down', remove_orphans=True)

    @accepts(Str('app_name'))
    @returns()
    def start(self, app_name):
        """
        Start `app_name` app.
        """
        app_config = self.middleware.call_sync('app.get_instance', app_name)
        compose_action(app_name, app_config['version'], 'up', force_recreate=True, remove_orphans=True)

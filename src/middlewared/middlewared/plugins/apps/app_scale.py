from middlewared.schema import accepts, Str, returns
from middlewared.service import Service

from .app_utils import get_version_in_use_of_app
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
        self.middleware.call_sync('app.get_instance', app_name)
        compose_action(app_name, get_version_in_use_of_app(app_name), 'down', remove_orphans=True)

    @accepts(Str('app_name'))
    @returns()
    def start(self, app_name):
        """
        Start `app_name` app.
        """
        self.middleware.call_sync('app.get_instance', app_name)
        compose_action(app_name, get_version_in_use_of_app(app_name), 'up', force_recreate=True, remove_orphans=True)

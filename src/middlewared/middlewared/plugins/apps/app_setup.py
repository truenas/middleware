from middlewared.service import Service


class AppSetupService(Service):

    class Config:
        namespace = 'app.setup'
        private = True

    def create_dirs(self, app_name, app_to_install):
        pass

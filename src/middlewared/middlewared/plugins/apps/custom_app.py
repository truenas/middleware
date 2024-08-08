from middlewared.service import Service


class AppCustomService(Service):

    class Config:
        namespace = 'app.custom'
        private = True

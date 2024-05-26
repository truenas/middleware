from middlewared.service import Service


class AppSchemaService(Service):

    class Config:
        namespace = 'app.schema'
        private = True

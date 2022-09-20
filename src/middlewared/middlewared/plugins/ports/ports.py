from middlewared.schema import accepts
from middlewared.service import Service


class PortService(Service):

    class Config:
        private = True



__author__ = 'jceel'

from namespace import Namespace

class SystemNamespace(Namespace):
    def commands(self):
        return [
            Command('logout', )
        ]

    def namespaces(self):
        pass
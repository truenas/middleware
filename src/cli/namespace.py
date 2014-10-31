__author__ = 'jceel'


class Namespace(object):
    def help(self):
        pass

    def commands(self):
        pass

    def namespaces(self):
        pass

    def on_enter(self):
        pass

    def on_leave(self):
        pass


class Command(object):
    def __init__(self, name, func, description):
        pass

    def run(self, args):
        pass


class RootNamespace(Namespace):
    pass
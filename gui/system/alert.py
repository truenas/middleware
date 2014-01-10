import imp
import os


class BaseAlertMetaclass(type):

    def __new__(cls, name, *args, **kwargs):
        klass = type.__new__(cls, name, *args, **kwargs)
        if name.endswith('Alert'):
            klass.name = name[:-5]
        return klass


class BaseAlert(object):

    __metaclass__ = BaseAlertMetaclass

    alert = None
    name = None

    def __init__(self, alert):
        self.alert = alert

    def run(self):
        raise NotImplementedError


class AlertPlugins(object):

    def __init__(self):
        self.basepath = os.path.abspath(
            os.path.dirname(__file__)
        )
        self.modspath = os.path.join(self.basepath, "alertmods/")
        self.mods = {}

    def rescan(self):
        self.mods.clear()
        for f in sorted(os.listdir(self.modspath)):
            if f.startswith('__') or not f.endswith('.py'):
                continue

            f = f.replace('.py', '')
            fp, pathname, description = imp.find_module(f, [self.modspath])

            try:
                imp.load_module(f, fp, pathname, description)
            finally:
                if fp:
                    fp.close()

    def register(self, klass):
        instance = klass(self)
        self.mods[instance] = {
            'lastrun': None,
        }
        print instance.name


alertPlugins = AlertPlugins()
alertPlugins.rescan()
alertPlugins.rescan()

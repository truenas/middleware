class Plugin(object):

    name = None

    def __init__(self, name):
        self.name = name

    def __setattr__(self, name, value):
        if not hasattr(self, name):
            raise ValueError(name)
        object.__setattr__(self, name, value)

    def __repr__(self):
        return '<Plugin: %s>' % self.name


class Available(object):

    def get_local(self):

        results = []

        results.append(
            Plugin(name="transmission")
        )

        return results

    def all(self):
        return self.get_local()

availablePlugins = Available()

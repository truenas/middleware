class Plugin(object):

    name = None
    description = None

    def __init__(self, name, description):
        self.name = name
        self.description = description

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
            Plugin(name="transmission", description="BitTorrent client")
        )

        return results

    def all(self):
        return self.get_local()

availablePlugins = Available()

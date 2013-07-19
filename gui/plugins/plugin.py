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
        results = [
            Plugin(name="Transmission", description="BitTorrent client"),
            Plugin(
                name="MiniDLNA",
                description="Multimedia streamer using DLNA",
            ),
            Plugin(
                name="Firefly",
                description="Audio media server for iTunes and Roku",
            ),
        ]

        return results

    def all(self):
        return self.get_local()

availablePlugins = Available()

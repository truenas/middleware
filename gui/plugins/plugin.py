import hashlib
import logging

import requests

log = logging.getLogger("plugins.plugin")


class Plugin(object):

    id = None
    name = None
    description = None
    version = None

    def __init__(self, name, description, version):
        self.id = hashlib.sha256("%s:%s" % (name, version)).hexdigest()
        self.name = name
        self.description = description
        self.version = version

    def __setattr__(self, name, value):
        if not hasattr(self, name):
            raise ValueError(name)
        object.__setattr__(self, name, value)

    def __repr__(self):
        return '<Plugin: %s>' % self.name


class Available(object):

    def get_local(self):
        results = [
            Plugin(
                name="Transmission",
                version="2.77",
                description="BitTorrent client",
            ),
            Plugin(
                name="MiniDLNA",
                version="1.0.51",
                description="Multimedia streamer using DLNA",
            ),
            Plugin(
                name="Firefly",
                version="2.5",
                description="Audio media server for iTunes and Roku",
            ),
        ]

        return results

    def get_remote(self, url):
        results = []

        log.debug("Retrieving available plugins from %s", url)
        r = requests.get(url)

        if r.status_code != requests.codes.ok:
            log.debug(
                "HTTP request to %s did not return OK (%d)", url, r.status_code
            )
            return results

        data = r.json()

        for p in data['plugins']:
            results.append(
                Plugin(
                    name=data['name'],
                    description=data['description'],
                    version=data['version'],
                )
            )

        return results

    def all(self):
        return self.get_local()

availablePlugins = Available()

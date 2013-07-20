import logging

import requests

log = logging.getLogger("plugins.plugin")


class Plugin(object):

    name = None
    description = None
    version = None
    hash = None
    urls = None

    def __init__(self, name, description, version, hash, urls=None):
        self.name = name
        self.description = description
        self.version = version
        self.hash = hash
        self.urls = urls

    def __setattr__(self, name, value):
        if not hasattr(self, name):
            raise ValueError(name)
        object.__setattr__(self, name, value)

    def __repr__(self):
        return '<Plugin: %s>' % self.name


class Available(object):

    def get_local(self):
        results = []

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
                Plugin(**p)
            )

        return results

    def all(self):
        return self.get_local()

availablePlugins = Available()

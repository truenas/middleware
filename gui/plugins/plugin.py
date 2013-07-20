import hashlib
import logging
import urllib2

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

    def download(self, path):
        if not self.urls:
            raise ValueError("Not downloadable")

        rv = False
        for url in self.urls:
            try:
                rv = self.__download(url, path)
                if rv:
                    break
            except Exception, e:
                raise
                log.debug(
                    "Failed to download %s (%s): %s",
                    url,
                    type(e).__class__,
                    e,
                )
        return rv

    def __download(self, url, path):
        response = urllib2.urlopen(url)
        try:
            total_size = int(
                response.info().getheader('Content-Length').strip()
            )
        except Exception, e:
            log.debug(
                "Error getting Content-Length header (%s): %s",
                type(e).__class__,
                e,
            )
            total_size = None

        csize = 20480
        downloaded = 0
        last_percent = 0

        with open(path, 'wb+') as f, open("/tmp/.plugininstall_progess", 'w') as f2:

            if total_size:
                f2.write("0\n")
                f2.flush()

            while True:
                chunk = response.read(csize)
                if not chunk:
                    break

                f.write(chunk)

                if total_size:
                    downloaded += len(chunk)
                    percent = float(downloaded) / total_size
                    percent = round(percent * 100, 2)
                    if int(percent) != last_percent:
                        f2.write("%d\n" % percent)
                        f2.flush()
                    last_percent = int(percent)

            if total_size and downloaded != total_size:
                return False

            f.seek(0)
            dohash = hashlib.sha256()
            while True:
                chunk = f.read(csize)
                if not chunk:
                    break
                dohash.update(chunk)
            if dohash.hexdigest() != self.hash:
                log.debug("SHA256 failed for %s", url)
                return False

        return True


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

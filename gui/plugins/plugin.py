import hashlib
import logging
import os
import platform
import re
import urllib2

from django.utils.translation import ugettext as _
from freenasUI.middleware.exceptions import MiddlewareError

import requests

PROGRESS_FILE = "/tmp/.plugininstall_progess"
log = logging.getLogger("plugins.plugin")


class Plugin(object):

    id = None
    arch = None
    name = None
    description = None
    version = None
    hash = None
    urls = None

    def __init__(self, id, name, description, arch, version, hash, urls=None):
        self.id = id
        self.arch = arch
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

    @property
    def unixname(self):
        return self.name.split(' ')[0].lower()

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
                log.debug(
                    "Failed to download %s (%s): %s",
                    url,
                    type(e).__class__,
                    e,
                )
                #FIXME: try to download from multiple urls
                raise MiddlewareError(_("Failed to download %s: %s" % (
                    url,
                    e,
                )))

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

        rv = True
        csize = 20480
        downloaded = 0
        last_percent = 0

        with open(path, 'wb+') as f, open(PROGRESS_FILE, 'w') as f2:

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

            if self.hash:
                log.debug("No hash provided to validate download (%r)", self)
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

        return rv


class Available(object):

    __cache = None

    def __init__(self):
        self.__cache = dict()

    def get_local(self):
        results = []

        return results

    def get_remote(self, url, cache=False):

        if cache and url in self.__cache:
            log.debug("Using cached results for %s", url)
            return self.__cache.get(url)

        results = []

        log.debug("Retrieving available plugins from %s", url)
        r = requests.get(url, timeout=8)

        if r.status_code != requests.codes.ok:
            log.debug(
                "HTTP request to %s did not return OK (%d)", url, r.status_code
            )
            return results

        data = r.json()

        for p in data:
            try:
                item = self._get_remote_item(p)
                if item is False:
                    continue
                results.append(item)
            except Exception, e:
                log.debug("Failed to get remote item: %s", e)

        self.__cache[url] = results

        return results

    def _get_remote_item(self, p):
        status = p['Status']
        if status['architecture'] != platform.machine():
            return False

        return Plugin(
            id=int(p['Pbi']['id']),
            name=p['Pbi']['title'],
            description=p['Pbi'].get("description", "Not implemented"),
            version=status['pbi_version'],
            arch=status['architecture'],
            hash=status.get('hash', None),
            urls=[status['location']],
        )

    def all(self):
        return self.get_local()


def get_available_plugins():
    from freenasUI.plugins import models, availablePlugins

    conf = models.Configuration.objects.latest('id')
    if conf and conf.collectionurl:
        url = conf.collectionurl
    else:
        url = models.PLUGINS_INDEX

    return availablePlugins.get_remote(url=url, cache=True)


def get_remote_plugin_by_oid(oid):
    from freenasUI.plugins import models, availablePlugins

    plugin = None
    for p in get_available_plugins(): 
        if p.id == int(oid):
            plugin = p
            break

    return plugin


def get_remote_plugin_pbiname_by_oid(oid):
    plugin = get_remote_plugin_by_oid(oid)
    if not plugin:
        return None

    pbiname = None
    for url in plugin.urls:
        parts = url.split('/')
        nparts = len(parts)
        pbiname = parts[0]
        if nparts > 0:
            pbiname = parts[nparts - 1]
        break

    if pbiname:
        pbiname = re.sub('\.pbi$', '', pbiname, flags=re.I)

    return pbiname


def get_remote_plugin_by_installed_oid(oid):
    from freenasUI.plugins import models

    rplugin = None
    iplugin = models.Plugins.objects.filter(id=oid)
    if iplugin: 
        iplugin = iplugin[0]

        for rp in get_available_plugins():
            pbiname = get_remote_plugin_pbiname_by_oid(rp.id)
            if not pbiname:
                continue

            if iplugin.plugin_arch.lower() == rp.arch.lower() and \
                iplugin.plugin_pbiname.lower() == pbiname.lower():
                rplugin = rp  
                break  

    return rplugin


def get_installed_plugin_update_status(oid):
    from freenasUI.plugins import models
    status = False

    iplugin = models.Plugins.objects.filter(id=oid)
    if iplugin: 
        iplugin = iplugin[0]

    rplugin = get_remote_plugin_by_installed_oid(oid)
    if rplugin and iplugin:
        if str(iplugin.plugin_version).lower() != str(rplugin.version).lower():
            status = True

    return status


def get_installed_plugins_by_remote_oid(oid):
    from freenasUI.plugins import models, availablePlugins
    iplugins = []

    pbiname = get_remote_plugin_pbiname_by_oid(oid)
    if not pbiname:
        return iplugins

    if pbiname:
        plugins = models.Plugins.objects.filter(
            plugin_arch=plugin.arch,
            plugin_pbiname=pbiname
        )

    return plugins


def get_installed_plugins_count_by_remote_oid(oid):
    icount = 0

    iplugins = get_installed_plugins_by_remote_oid(oid)
    if iplugins:
        icount = len(iplugins)

    return icount


availablePlugins = Available()

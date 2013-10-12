import hashlib
import logging
import os
import platform
import requests
import re
import urllib2

from django.utils.translation import ugettext as _

from freenasUI.common import pbi
from freenasUI.middleware.exceptions import MiddlewareError

import platform as p
if p.machine() == 'amd64':
    __arch = 'x64'
else:
    __arch = 'x32'

PLUGINS_INDEX = 'http://www.freenas.org/downloads/plugins/9/%s' % __arch
PLUGINS_META = '%s/pbi-meta' % PLUGINS_INDEX
PLUGINS_REPO = '%s/pbi-repo.rpo' % PLUGINS_META

PROGRESS_FILE = "/tmp/.plugininstall_progess"
log = logging.getLogger("plugins.plugin")


class Plugin(object):

    repo_id = None
    application = None
    version = None
    category = None
    created = None
    rootinstall = None
    arch = None
    author = None
    url = None
    license = None
    type = None
    keywords = None
    icon = None
    description = None
    sha256 = None
    file = None
    icon = None
    hash = None
    urls = None
    size = None

    def __init__(
        self, repo_id, application, version, category, created,
        rootinstall, arch, author, url, license, type, keywords, icon,
        description, sha256, file, hash, urls, size
    ):

        self.repo_id = repo_id
        self.application = application
        self.version = version
        self.category = category
        self.created = created
        self.rootinstall = rootinstall
        self.arch = arch
        self.author = author
        self.url = url
        self.license = license
        self.type = type
        self.keywords = keywords
        self.icon = icon
        self.description = description
        self.sha256 = sha256
        self.file = file
        self.hash = hash
        self.urls = urls
        self.size = size

    def __setattr__(self, application, value):
        if not hasattr(self, application):
            raise ValueError(application)
        object.__setattr__(self, application, value)

    def __repr__(self):
        return '<Plugin: %s>' % self.application

    @property
    def id(self):
        return self.hash

    @property
    def name(self):
        return self.application

    @property
    def unixname(self):
        return self.application.split(' ')[0].lower()

    def download(self, path):
        if not self.repo_id:
            raise ValueError("Not downloadable")
        if not self.urls:
            raise ValueError("No mirrors available")

        rv = False
        for url in self.urls:
            rpath = "%s/%s" % (url, self.file)
            try:
                rv = self.__download(rpath, path)
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
    __repo_id = None
    __repo_desc = None
    __def_repo = None

    def __init__(self):
        self.__cache = dict()

    def _def_repo_id(self, repo_id=None):
        """
        Make sure the call to get_repo is retarded as much as possible.

        Available is a class that is instantiated on the very beginning
        of django bootstrap process, so we want to avoid unnecessary calls
        for all the tools involved (autorepl, autosnap, syncdisks, webshell).

        The method get_repo will result in a unix process fork for pbi_listrepo
        that won't be available in a complete install.
        """
        if self.__def_repo is not None:
            return self.__repo_id
        self.__def_repo = True
        repo = self.get_repo(repo_id=repo_id, create=True)
        if repo:
            self.__repo_id = repo[0]
            self.__repo_desc = repo[1]
        return self.__repo_id

    def create_repo(self):
        from freenasUI.middleware.notifier import notifier
        url = PLUGINS_REPO
        rpath = "/var/tmp/pbi-repo.rpo"

        r = requests.get(url, timeout=8)
        if r.status_code != requests.codes.ok:
            return False

        with open(rpath, "w") as f:
            for byte in r:
                f.write(byte)
            f.close()

        p = pbi.PBI()

        out = p.addrepo(repofile=rpath)
        if not out:
            return False

        notifier().restart("pbid")
        return True

    def get_repo(self, repo_id=None, create=False):
        p = pbi.PBI()

        if repo_id:
            repos = p.listrepo(repoid=repo_id)
        else:
            repos = p.listrepo()

        if not repos and create is False:
            return None

        elif not repos and create is True:
            if not self.create_repo():
                return None
            repos = p.listrepo()

        elif repos and repo_id is not None:
            for repo in repos:
                return repo

        for repo in repos:
            #repoid = repo[0]
            description = repo[1]
            if re.match('Official FreeNAS Repository', description, re.I):
                return repo

        if create is True:
            if not self.create_repo():
                return None

            repos = p.listrepo()
            if not repos:
                return None

        for repo in repos:
            #repoid = repo[0]
            description = repo[1]
            if re.match('Official FreeNAS Repository', description, re.I):
                return repo

        return None

    def get_mirror_urls(self, repo_id):
        reposdir = "/var/db/pbi/repos"
        mirrorsdir = "/var/db/pbi/mirrors"

        if not repo_id:
            repo_id = self._def_repo_id()
            if not repo_id:
                return None

        urls = []
        for f in os.listdir(reposdir):
            parts = f.split('.')
            if not parts:
                continue
            id = parts[0]
            if id == repo_id:
                fp = "%s/%s" % (mirrorsdir, parts[1])
                with open(fp, "r") as mirrors:
                    for line in mirrors:
                        mirror = line.strip()
                        urls.append(mirror)
                    mirrors.close()

        return urls

    def get_index_entry(
        self, repo_id=None, application=None, arch=None, version=None
    ):
        reposdir = "/var/db/pbi/repos"
        indexdir = "/var/db/pbi/index"

        if not application or not version:
            return None

        if not repo_id:
            repo_id = self._def_repo_id()
            if not repo_id:
                return None

        sha256 = None
        for f in os.listdir(reposdir):
            parts = f.split('.')
            if not parts:
                continue
            id = parts[0]
            if id == repo_id:
                sha256 = parts[1]
                break

        if sha256:
            try:
                indexfile = "%s/%s-index" % (indexdir, sha256)
                with open(indexfile, "r") as f:
                    for line in f:
                        parts = line.split(':')
                        if (
                            parts[0] == application.lower() and
                            parts[1] == arch.lower() and
                            parts[2] == version.lower()
                        ):
                            return parts
                    f.close()

            except Exception:
                log.debug("Unable to open up repo with sha256: %s", sha256)
                return None

        return None

    def get_icon(self, repo_id=None, oid=None):

        icon_path = None
        available = self.get_remote(repo_id=None, cache=True)
        for p in available:
            if p.id == oid:
                icon_path = p.icon
                break

        icon = None
        if icon_path:
            try:
                with open(icon_path, 'r') as f:
                    icon = f.read()
                    f.close()

            except:
                log.debug("Unable to open icon %s", icon_path)
                icon = None

        return icon

    def get_update_status(self, oid):
        from freenasUI.plugins import models
        status = False

        iplugin = models.Plugins.objects.filter(id=oid)
        if iplugin:
            iplugin = iplugin[0]

        rplugin = None
        for rp in self.get_remote(cache=True):
            if rp.name == iplugin.plugin_name:
                rplugin = rp
                break

        if rplugin and iplugin:
            if str(iplugin.plugin_version).lower() != str(rplugin.version).lower():
                status = True

        return status

    def get_local(self):
        results = []

        return results

    def get_remote(self, repo_id=None, cache=False):
        if not repo_id:
            repo_id = self._def_repo_id()
        if cache and repo_id in self.__cache:
            log.debug("Using cached results for %s", repo_id)
            return self.__cache.get(repo_id)

        log.debug("Retrieving available plugins from repo %s", repo_id)

        p = pbi.PBI()
        results = p.browser(repo_id=repo_id, flags=pbi.PBI_BROWSER_FLAGS_VIEWALL)
        if not results:
            log.debug(
                "No results returned for repo %s", repo_id
            )
            return results

        plugins = []
        for p in results:
            try:
                index_entry = self.get_index_entry(
                    repo_id,
                    application=p['Application'],
                    arch=p['Arch'],
                    version=p['Version']
                )
                if not index_entry:
                    log.debug("not index entry found for %s", p['Application'])
                    continue

                urls = self.get_mirror_urls(repo_id)

                item = self._get_remote_item(repo_id, p, index_entry, urls)
                if item is False:
                    log.debug("unable to create plugin for %s", p['Application'])
                    continue

                plugins.append(item)
            except Exception as e:
                log.debug("Failed to get remote item: %s", e)

        self.__cache[repo_id] = plugins
        return plugins

    def _get_remote_item(self, repo_id, p, ie, urls):
        arch = p['Arch']
        if arch != platform.machine():
            return False

        return Plugin(
            repo_id=repo_id,
            application=p['Application'],
            version=p['Version'],
            category=p['Category'],
            created=p['Created'],
            rootinstall=p['RootInstall'],
            arch=p['Arch'],
            author=p['Author'],
            url=p['URL'],
            license=p['License'],
            type=p['Type'],
            keywords=p['Keywords'],
            icon=p['Icon'],
            description=p['Description'],
            sha256=ie[3],
            file=ie[5],
            hash=ie[3],
            urls=urls,
            size=(long(ie[9])*1024)
        )

    def all(self):
        return self.get_local()


availablePlugins = Available()

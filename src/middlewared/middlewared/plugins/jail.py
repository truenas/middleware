import os

from middlewared.service import Service
# iocage's imports are per command, these are just general facilities
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_json import IOCJson


class JailService(Service):

    def __init__(self, *args):
        super(JailService, self).__init__(*args)
        self.__list = None
        self.jails, self.paths = IOCList("uuid").list_datasets()

    def check_jail_existence(self, jail):
        _jail = {tag: uuid for (tag, uuid) in self.jails.items() if
                 uuid.startswith(jail) or tag == jail}

        if len(_jail) == 1:
            tag, uuid = next(iter(_jail.items()))
            path = self.paths[tag]

            return tag, uuid, path
        elif len(_jail) > 1:
            return "Multiple jails found for {}:".format(jail)
        else:
            return "{} not found!".format(jail)

    def list(self, lst_type, options={}):
        """Lists either 'all', 'base', 'template'"""
        if lst_type == "release":
            lst_type = "base"

        full = options.get("full", False)
        hdr = options.get("header", False)

        if lst_type == "plugins":
            from iocage.lib.ioc_fetch import IOCFetch
            self.__list = IOCFetch("").fetch_plugin_index("", _list=True)
        else:
            self.__list = IOCList(lst_type, hdr, full).list_datasets()

        return self.__list

    def set(self, jail, options):
        """Sets a jail property."""
        prop = options.get("prop", None)
        plugin = options.get("plugin", False)

        tag, uuid, path = self.check_jail_existence(jail)

        if "template" in prop.split("=")[0]:
            if "template" in path and prop != "template=no":
                return f"{uuid} ({tag}) is already a template!"
            elif "template" not in path and prop != "template=yes":
                return f"{uuid} ({tag}) is already a jail!"

        if plugin:
            _prop = prop.split(".")
            return IOCJson(path, cli=True).json_plugin_set_value(_prop)

        IOCJson(path, cli=True).json_set_value(prop)

        return f"{prop} set."

    def get(self, jail, options):
        """Gets a jail property."""
        prop = options.get("prop", None)
        plugin = options.get("plugin", False)

        tag, uuid, path = self.check_jail_existence(jail)

        if "template" in prop.split("=")[0]:
            if "template" in path and prop != "template=no":
                return f"{uuid} ({tag}) is already a template!"
            elif "template" not in path and prop != "template=yes":
                return f"{uuid} ({tag}) is already a jail!"

        if plugin:
            _prop = prop.split(".")
            return IOCJson(path).json_plugin_set_value(_prop)

        if prop == "all":
            return IOCJson(path).json_get_value(prop)
        elif prop == "state":
            status, _ = IOCList.list_get_jid(path.split("/")[3])

            if status:
                return "up"
            else:
                return "down"

        return IOCJson(path).json_get_value(prop)

    def fetch(self, options):
        """Fetches a release or plugin."""
        from iocage.lib.ioc_fetch import IOCFetch

        release = options.get("release", None)
        server = options.get("server", "ftp.freebsd.org")
        user = options.get("user", "anonymous")
        password = options.get("password", "anonymous@")
        plugin_file = options.get("plugin_file", None)
        props = options.get("props", None)

        if plugin_file:
            IOCFetch("", server, user, password).fetch_plugin(plugin_file,
                                                              props, 0)
            return f"{plugin_file} fetched."

        IOCFetch(release, server, user, password).fetch_release()

        return f"{release} fetched."

    def destroy(self, jail):
        """Takes a jail and destroys it."""
        from iocage.lib.ioc_destroy import IOCDestroy

        tag, uuid, path = self.check_jail_existence(jail)
        conf = IOCJson(path).json_load()
        status, _ = IOCList().list_get_jid(uuid)

        if status:
            from iocage.lib.ioc_stop import IOCStop
            IOCStop(uuid, tag, path, conf, silent=True)

        IOCDestroy(uuid, tag, path).destroy_jail()

        return f"{jail} destroyed."

    def start(self, jail):
        """Takes a jail and starts it."""
        from iocage.lib.ioc_start import IOCStart

        tag, uuid, path = self.check_jail_existence(jail)
        conf = IOCJson(path).json_load()
        status, _ = IOCList().list_get_jid(uuid)

        if not status:
            if conf["type"] in ("jail", "plugin"):
                IOCStart(uuid, tag, path, conf)
                start = "{} started".format(jail)
            else:
                start = f"{jail} must be type jail or plugin to be started"
        else:
            start = "{} already running.".format(jail)

        return start

    def stop(self, jail):
        """Takes a jail and stops it."""
        from iocage.lib.ioc_stop import IOCStop

        tag, uuid, path = self.check_jail_existence(jail)
        conf = IOCJson(path).json_load()
        status, _ = IOCList().list_get_jid(uuid)

        if status:
            if conf["type"] in ("jail", "plugin"):
                IOCStop(uuid, tag, path, conf)
                stop = "{} stopped".format(jail)
            else:
                stop = "{} must be type jail or plugin to be stopped".format(jail)
        else:
            stop = "{} already stopped".format(jail)

        return stop

    def create(self, options):
        """Creates a jail."""
        from iocage.lib.ioc_create import IOCCreate

        release = options.get("release", None)
        template = options.get("template", None)
        pkglist = options.get("pkglist", None)
        uuid = options.get("uuid", None)
        basejail = options.get("basejail", False)
        empty = options.get("empty", False)
        short = options.get("short", False)
        props = options.get("props", [])
        pool = IOCJson().json_get_value("pool")
        iocroot = IOCJson(pool).json_get_value("iocroot")

        if template:
            release = template

        if not os.path.isdir(f"{iocroot}/releases/{release}") and not \
                template and not empty:
            from iocage.lib.ioc_fetch import IOCFetch
            IOCFetch(release).fetch_release()

        _uuid = IOCCreate(release, props, 0, pkglist,
                          template=template, short=short, uuid=uuid,
                          basejail=basejail, empty=empty).create_jail()

        return f"{_uuid} created."

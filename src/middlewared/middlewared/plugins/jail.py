import os

from iocage.lib.ioc_json import IOCJson
# iocage's imports are per command, these are just general facilities
from iocage.lib.ioc_list import IOCList
from middlewared.schema import Bool, Dict, List, Str, accepts
from middlewared.service import Service, job, private


class JailService(Service):

    def __init__(self, *args):
        super(JailService, self).__init__(*args)

    @private
    def check_dataset_existence(self):
        from iocage.lib.ioc_check import IOCCheck

        IOCCheck()

    @private
    def check_jail_existence(self, jail):
        self.check_dataset_existence()

        jails, paths = IOCList("uuid").list_datasets()
        _jail = {tag: uuid for (tag, uuid) in jails.items() if
                 uuid.startswith(jail) or tag == jail}

        if len(_jail) == 1:
            tag, uuid = next(iter(_jail.items()))
            path = paths[tag]

            return tag, uuid, path
        elif len(_jail) > 1:
            raise RuntimeError("Multiple jails found for {}:".format(jail))
        else:
            raise RuntimeError("{} not found!".format(jail))

    @accepts(Str("lst_type", enum=["ALL", "RELEASE", "BASE", "TEMPLATE"]),
             Dict("options",
                  Bool("full"),
                  Bool("header"),
                  ))
    def list(self, lst_type, options=None):
        """Lists either 'all', 'base', 'template'"""
        self.check_dataset_existence()

        lst_type = lst_type.lower()

        if options is None:
            options = {}

        if lst_type == "release":
            lst_type = "base"

        full = options.get("full", True)
        hdr = options.get("header", False)

        if lst_type == "plugins":
            from iocage.lib.ioc_fetch import IOCFetch

            _list = IOCFetch("").fetch_plugin_index("", _list=True)
        else:
            _list = IOCList(lst_type, hdr, full).list_datasets()

        return _list

    @accepts(Str("jail"), Dict("options",
                               Str("prop"),
                               Bool("plugin"),
                               ))
    def set(self, jail, options):
        """Sets a jail property."""
        prop = options["prop"]
        plugin = options["plugin"]

        tag, uuid, path = self.check_jail_existence(jail)

        if "template" in prop.split("=")[0]:
            if "template" in path and prop != "template=no":
                raise RuntimeError(f"{uuid} ({tag}) is already a template!")
            elif "template" not in path and prop != "template=yes":
                raise RuntimeError(f"{uuid} ({tag}) is already a jail!")

        if plugin:
            _prop = prop.split(".")

            return IOCJson(path, cli=True).json_plugin_set_value(_prop)

        IOCJson(path, cli=True).json_set_value(prop)

        return True

    @accepts(Str("jail"), Dict("options",
                               Str("prop"),
                               Bool("plugin"),
                               ))
    def get(self, jail, options):
        """Gets a jail property."""
        prop = options["prop"]
        plugin = options["plugin"]

        tag, uuid, path = self.check_jail_existence(jail)

        if "template" in prop.split("=")[0]:
            if "template" in path and prop != "template=no":
                raise RuntimeError(f"{uuid} ({tag}) is already a template!")
            elif "template" not in path and prop != "template=yes":
                raise RuntimeError(f"{uuid} ({tag}) is already a jail!")

        if plugin:
            _prop = prop.split(".")
            return IOCJson(path).json_plugin_set_value(_prop)

        if prop == "all":
            return IOCJson(path).json_get_value(prop)
        elif prop == "state":
            status, _ = IOCList.list_get_jid(path.split("/")[3])

            if status:
                return "UP"
            else:
                return "DOWN"

        return IOCJson(path).json_get_value(prop)

    @accepts(Dict("options",
                  Str("release"),
                  Str("server", default="ftp.freebsd.org"),
                  Str("user", default="anonymous"),
                  Str("password", default="anonymous@"),
                  Str("plugin_file"),
                  Str("props"),
                  ))
    @job(lock=lambda args: f"jail_fetch:{args[-1]}")
    def fetch(self, job, options):
        """Fetches a release or plugin."""
        from iocage.lib.ioc_fetch import IOCFetch
        self.check_dataset_existence()

        release = options["release"]
        server = options["server"]
        user = options["user"]
        password = options["password"]
        plugin_file = options["plugin_file"]
        props = options["props"]

        if plugin_file:
            IOCFetch("", server, user, password).fetch_plugin(plugin_file,
                                                              props, 0)
            return True

        IOCFetch(release, server, user, password).fetch_release()

        return True

    @accepts(Str("jail"))
    def destroy(self, jail):
        """Takes a jail and destroys it."""
        from iocage.lib.ioc_destroy import IOCDestroy

        _, uuid, path = self.check_jail_existence(jail)
        conf = IOCJson(path).json_load()
        status, _ = IOCList().list_get_jid(uuid)

        if status:
            from iocage.lib.ioc_stop import IOCStop
            IOCStop(uuid, tag, path, conf, silent=True)

        IOCDestroy().destroy_jail(path)

        return True

    @accepts(Str("jail"))
    def start(self, jail):
        """Takes a jail and starts it."""
        from iocage.lib.ioc_start import IOCStart

        tag, uuid, path = self.check_jail_existence(jail)
        conf = IOCJson(path).json_load()
        status, _ = IOCList().list_get_jid(uuid)

        if not status:
            if conf["type"] in ("jail", "plugin"):
                IOCStart(uuid, tag, path, conf)

                return True
            else:
                raise RuntimeError(f"{jail} must be type jail or plugin to"
                                   " be started")
        else:
            raise RuntimeError(f"{jail} already running.")

    @accepts(Str("jail"))
    def stop(self, jail):
        """Takes a jail and stops it."""
        from iocage.lib.ioc_stop import IOCStop

        tag, uuid, path = self.check_jail_existence(jail)
        conf = IOCJson(path).json_load()
        status, _ = IOCList().list_get_jid(uuid)

        if status:
            if conf["type"] in ("jail", "plugin"):
                IOCStop(uuid, tag, path, conf)

                return True
            else:
                raise RuntimeError(f"{jail} must be type jail or plugin to"
                                   " be stopped")
        else:
            raise RuntimeError(f"{jail} already stopped")

    @accepts(Dict("options",
                  Str("release"),
                  Str("template"),
                  Str("pkglist"),
                  Str("uuid"),
                  Bool("basejail"),
                  Bool("empty"),
                  Bool("short"),
                  List("props"),
                  ))
    @job()
    def create(self, job, options):
        """Creates a jail."""
        from iocage.lib.ioc_create import IOCCreate
        self.check_dataset_existence()

        release = options["release"]
        template = options["template"]
        pkglist = options["pkglist"]
        uuid = options["uuid"]
        basejail = options["basejail"]
        empty = options["empty"]
        short = options["short"]
        props = options["props"]
        pool = IOCJson().json_get_value("pool")
        iocroot = IOCJson(pool).json_get_value("iocroot")

        if template:
            release = template

        if not os.path.isdir(f"{iocroot}/releases/{release}") and not \
                template and not empty:
            self.middleware.call('jail.fetch', {"release": release}).wait()

        IOCCreate(release, props, 0, pkglist, template=template,
                  short=short, uuid=uuid, basejail=basejail,
                  empty=empty).create_jail()

        return True

    @accepts(Str("jail"), Dict("options",
                  Str("action"),
                  Str("source"),
                  Str("destination"),
                  Str("fstype"),
                  Str("fsoptions"),
                  Str("dump"),
                  Str("_pass"),
                  ))
    def fstab(self, jail, options):
        """
        Adds an fstab mount to the jail, mounts if the jail is running.
        """
        from iocage.lib.ioc_fstab import IOCFstab
        self.check_dataset_existence()

        tag, uuid, path = self.check_jail_existence(jail)
        action = options["action"]
        source = options["source"]
        destination = options["destination"]
        fstype = options["fstype"]
        fsoptions = options["fsoptions"]
        dump = options["dump"]
        _pass = options["_pass"]

        IOCFstab(uuid, tag, action, source, destination, fstype, fsoptions,
                 dump, _pass)

        return True

    @accepts(Str("pool"))
    def activate(self, pool):
        """Activates a pool for iocage usage, and deactivates the rest."""
        import libzfs

        zfs = libzfs.ZFS(history=True, history_prefix="<iocage>")
        pools = zfs.pools
        prop = "org.freebsd.ioc:active"

        for _pool in pools:
            if _pool.name == pool:
                ds = zfs.get_dataset(_pool.name)
                ds.properties[prop] = libzfs.ZFSUserProperty("yes")
            else:
                ds = zfs.get_dataset(_pool.name)
                ds.properties[prop] = libzfs.ZFSUserProperty("no")

        return True

    @accepts(Str("ds_type", enum=["ALL", "JAIL", "TEMPLATE", "RELEASE"]))
    def clean(self, ds_type):
        """Cleans all iocage datasets of ds_type"""
        from iocage.lib.ioc_clean import IOCClean

        if ds_type == "JAIL":
            IOCClean().clean_jails()
        elif ds_type == "ALL":
            IOCClean().clean_all()
        elif ds_type == "RELEASE":
            pass
        elif ds_type == "TEMPLATE":
            IOCClean().clean_templates()

        return True

    @accepts(Str("jail"), List("command"), Dict("options",
                                                Str("host_user",
                                                    default="root"),
                                                Str("jail_user")))
    def exec(self, jail, command, options):
        """Issues a command inside a jail."""
        from iocage.lib.ioc_exec import IOCExec

        tag, uuid, path = self.check_jail_existence(jail)
        host_user = options["host_user"]
        jail_user = options["jail_user"]

        # We may be getting ';', '&&' and so forth. Adding the shell for
        # safety.
        if len(command) == 1:
            command = ["/bin/sh", "-c"] + command

        msg, _ = IOCExec(command, uuid, tag, path, host_user,
                         jail_user).exec_jail()

        return msg.decode("utf-8")

    @accepts(Str("jail"))
    @job(lock=lambda args: f"jail_update:{args[-1]}")
    def update(self, job, jail):
        """Updates specified jail to latest patch level."""
        from iocage.lib.ioc_fetch import IOCFetch

        tag, uuid, path = self.check_jail_existence(jail)
        status, jid = IOCList.list_get_jid(uuid)
        conf = IOCJson(path).json_load()
        started = False

        if conf["type"] == "jail":
            if not status:
                self.start(jail)
                started = True
        else:
            return False

        IOCFetch(conf["cloned_release"]).fetch_update(True, uuid, tag)

        if started:
            self.stop(jail)

        return True

    @accepts(Str("jail"), Str("release"))
    @job(lock=lambda args: f"jail_upgrade:{args[-1]}")
    def upgrade(self, job, jail, release):
        """Upgrades specified jail to specified RELEASE."""
        from iocage.lib.ioc_upgrade import IOCUpgrade

        tag, uuid, path = self.check_jail_existence(jail)
        status, jid = IOCList.list_get_jid(uuid)
        conf = IOCJson(path).json_load()
        root_path = f"{path}/root"
        started = False

        if conf["type"] == "jail":
            if not status:
                self.start(jail)
                started = True
        else:
            return False

        IOCUpgrade(conf, release, root_path).upgrade_jail()

        if started:
            self.stop(jail)

        return True

    @accepts(Str("jail"))
    @job(lock=lambda args: f"jail_export:{args[-1]}")
    def export(self, job, jail):
        """Exports jail to zip file"""
        from iocage.lib.ioc_image import IOCImage
        tag, uuid, path = self.check_jail_existence(jail)
        status, jid = IOCList.list_get_jid(uuid)
        started = False

        if status:
            self.stop(jail)
            started = True

        IOCImage().export_jail(uuid, tag, path)

        if started:
            self.start(jail)

        return True

    @accepts(Str("jail"))
    @job(lock=lambda args: f"jail_import:{args[-1]}")
    def _import(self, job, jail):
        """Imports jail from zip file"""
        from iocage.lib.ioc_image import IOCImage

        IOCImage().import_jail(jail)

        return True

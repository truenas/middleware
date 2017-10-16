import os

import iocage.lib.iocage as ioc
import libzfs
from iocage.lib.ioc_check import IOCCheck
from iocage.lib.ioc_clean import IOCClean
from iocage.lib.ioc_fetch import IOCFetch
from iocage.lib.ioc_image import IOCImage
from iocage.lib.ioc_json import IOCJson
# iocage's imports are per command, these are just general facilities
from iocage.lib.ioc_list import IOCList
from iocage.lib.ioc_upgrade import IOCUpgrade
from middlewared.schema import Bool, Dict, List, Str, accepts
from middlewared.service import CRUDService, filterable, job, private
from middlewared.utils import filter_list


class JailService(CRUDService):

    @filterable
    async def query(self, filters=None, options=None):
        options = options or {}
        jails = []
        try:
            jails = [
                list(jail.values())[0]

                for jail in ioc.IOCage().get("all", recursive=True)
            ]
        except BaseException:
            # Brandon is working on fixing this generic except, till then I
            # am not going to make the perfect the enemy of the good enough!
            self.logger.debug("iocage failed to fetch jails", exc_info=True)
            pass

        return filter_list(jails, filters, options)

    @accepts(
        Dict("options",
             Str("release"),
             Str("template"),
             Str("pkglist"),
             Str("uuid"),
             Bool("basejail"), Bool("empty"), Bool("short"), List("props")))
    async def do_create(self, options):
        """Creates a jail."""
        # Typically one would return the created jail's id in this
        # create call BUT since jail creation may or may not involve
        # fetching a release, which in turn could be time consuming
        # and could then block for a long time. This dictates that we
        # make it a job, but that violates the principle that CRUD methods
        # are not jobs as yet, so I settle on making this a wrapper around
        # the main job that calls this and return said job's id instead of
        # the created jail's id

        return await self.middleware.call('jail.create_job', options)

    @private
    @accepts(
        Dict("options",
             Str("release"),
             Str("template"),
             Str("pkglist"),
             Str("uuid"),
             Bool("basejail"), Bool("empty"), Bool("short"), List("props")))
    @job()
    def create_job(self, job, options):
        iocage = ioc.IOCage(skip_jails=True)

        release = options["release"]
        template = options.get("template", False)
        pkglist = options.get("pkglist", None)
        uuid = options.get("uuid", None)
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
            self.middleware.call_sync('jail.fetch', {"release":
                                                     release}).wait()

        iocage.create(
            release,
            props,
            0,
            pkglist,
            template=template,
            short=short,
            _uuid=uuid,
            basejail=basejail,
            empty=empty)

        return True

    @accepts(Str("jail"), Dict(
        "options",
        Str("prop"),
        Bool("plugin"), ))
    def do_update(self, jail, options):
        """Sets a jail property."""
        iocage = ioc.IOCage(skip_jails=True, jail=jail)

        prop = options["prop"]
        plugin = options["plugin"]

        iocage.set(prop, plugin)

        return True

    @accepts(Str("jail"))
    def do_delete(self, jail):
        """Takes a jail and destroys it."""
        iocage = ioc.IOCage(skip_jails=True, jail=jail)

        # TODO: Port children checking, release destroying.
        iocage.destroy_jail()

        return True

    @private
    def check_dataset_existence(self):
        IOCCheck()

    @private
    def check_jail_existence(self, jail):
        """Wrapper for iocage's API, as a few commands aren't ported to it"""
        iocage = ioc.IOCage(skip_jails=True, jail=jail)
        jail, path = iocage.__check_jail_existence__()

        return jail, path

    @accepts(
        Dict("options",
             Str("release"),
             Str("server", default="ftp.freebsd.org"),
             Str("user", default="anonymous"),
             Str("password", default="anonymous@"),
             Str("plugin_file"),
             Str("props"),
             List(
                 "files",
                 default=["MANIFEST", "base.txz", "lib32.txz", "doc.txz"])))
    @job(lock=lambda args: f"jail_fetch:{args[-1]}")
    def fetch(self, job, options):
        """Fetches a release or plugin."""
        self.check_dataset_existence()  # Make sure our datasets exist.
        iocage = ioc.IOCage()

        iocage.fetch(**options)

        return True

    @accepts(Str("jail"))
    def start(self, jail):
        """Takes a jail and starts it."""
        iocage = ioc.IOCage(skip_jails=True, jail=jail)

        iocage.start()

        return True

    @accepts(Str("jail"))
    def stop(self, jail):
        """Takes a jail and stops it."""
        iocage = ioc.IOCage(skip_jails=True, jail=jail)

        iocage.stop()

        return True

    @accepts(
        Str("jail"),
        Dict(
            "options",
            Str("action"),
            Str("source"),
            Str("destination"),
            Str("fstype"),
            Str("fsoptions"),
            Str("dump"),
            Str("_pass"), ))
    def fstab(self, jail, options):
        """
        Adds an fstab mount to the jail, mounts if the jail is running.
        """
        iocage = ioc.IOCage(jail=jail)

        action = options["action"]
        source = options["source"]
        destination = options["destination"]
        fstype = options["fstype"]
        fsoptions = options["fsoptions"]
        dump = options["dump"]
        _pass = options["_pass"]

        iocage.fstab(action, source, destination, fstype, fsoptions, dump,
                     _pass)

        return True

    @accepts(Str("pool"))
    def activate(self, pool):
        """Activates a pool for iocage usage, and deactivates the rest."""
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

        if ds_type == "JAIL":
            IOCClean().clean_jails()
        elif ds_type == "ALL":
            IOCClean().clean_all()
        elif ds_type == "RELEASE":
            pass
        elif ds_type == "TEMPLATE":
            IOCClean().clean_templates()

        return True

    @accepts(
        Str("jail"),
        List("command"),
        Dict("options", Str("host_user", default="root"), Str("jail_user")))
    def exec(self, jail, command, options):
        """Issues a command inside a jail."""

        iocage = ioc.IOCage(jail=jail)
        host_user = options["host_user"]
        jail_user = options.get("jail_user", None)

        # We may be getting ';', '&&' and so forth. Adding the shell for
        # safety.

        if len(command) == 1:
            command = ["/bin/sh", "-c"] + command

        host_user = "" if jail_user and host_user == "root" else host_user
        msg = iocage.exec(command, host_user, jail_user, return_msg=True)

        return msg.decode("utf-8")

    @accepts(Str("jail"))
    @job(lock=lambda args: f"jail_update:{args[-1]}")
    def update_jail_to_latest_patch(self, job, jail):
        """Updates specified jail to latest patch level."""

        uuid, path = self.check_jail_existence(jail)
        status, jid = IOCList.list_get_jid(uuid)
        conf = IOCJson(path).json_load()
        started = False

        if conf["type"] == "jail":
            if not status:
                self.start(jail)
                started = True
        else:
            return False

        IOCFetch(conf["cloned_release"]).fetch_update(True, uuid)

        if started:
            self.stop(jail)

        return True

    @accepts(Str("jail"), Str("release"))
    @job(lock=lambda args: f"jail_upgrade:{args[-1]}")
    def upgrade(self, job, jail, release):
        """Upgrades specified jail to specified RELEASE."""

        uuid, path = self.check_jail_existence(jail)
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
        uuid, path = self.check_jail_existence(jail)
        status, jid = IOCList.list_get_jid(uuid)
        started = False

        if status:
            self.stop(jail)
            started = True

        IOCImage().export_jail(uuid, path)

        if started:
            self.start(jail)

        return True

    @accepts(Str("jail"))
    @job(lock=lambda args: f"jail_import:{args[-1]}")
    def _import(self, job, jail):
        """Imports jail from zip file"""

        IOCImage().import_jail(jail)

        return True

#!/usr/local/bin/python
# Copyright 2017 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################
import asyncio
import datetime
import functools
import getopt
import json
import os
import subprocess as su
import sys
from concurrent.futures import ThreadPoolExecutor

import libzfs
import shutil
import pathlib
from middlewared.client import Client, ClientException


class Connection(object):
    def __enter__(self):
        self.client = Client()

        return self.client

    def __exit__(self, typ, value, traceback):
        self.client.close()

        if typ is not None:
            raise ()


class ZFS(object):
    def __init__(self, pool, dataset, zfs, verbose):
        self.dataset = dataset
        self.pool = pool
        self.jail = dataset.rsplit("/", 1)[-1]
        self.zfs = zfs
        self.verbose = verbose

    def pool_exists(self):
        """
        :return: True if pool exists
        """
        pools = list(self.zfs.pools)
        match = False

        for pool in pools:
            if pool.name == self.pool:
                if pool.status != "UNAVAIL":
                    match = True
                else:
                    raise RuntimeError(
                        f"ZFS pool '{self.pool}' is UNAVAIL!\n"
                        f"Please check zpool status {self.pool} for more"
                        " information.")

        return True if match else False

    def jail_exists(self):
        """
        :return: True if jail exists
        """
        try:
            self.zfs.get_dataset(f"{self.pool}/iocage/jails/{self.jail}")
        except libzfs.ZFSException as e:
            if e.code == libzfs.Error.NOENT:
                return False
            else:
                raise

        return True

    def send_dataset(self, send_fd, warden_dataset, date):
        fromsnap = f"WardenMigration_{date}"

        iocage_root = self.zfs.get_dataset(f"{self.pool}/iocage/jails/"
                                           f"{self.jail}/root")
        # We don't want this dataset anymore.
        iocage_root.umount()
        iocage_root.delete()

        try:
            warden_dataset.snapshot(
                f"{warden_dataset.name}@WardenMigration_{date}",
                recursive=True)
        except libzfs.ZFSException as e:
            if e.code == libzfs.Error.EXISTS:
                pass  # Snapshot exists.
            else:
                raise

        try:
            warden_dataset.send(
                send_fd,
                fromname=None,
                toname=fromsnap,
                flags={
                    None if not self.verbose else libzfs.SendFlag.PROGRESS,
                    libzfs.SendFlag.PROPS
                }
            )
        finally:
            try:
                os.close(send_fd)
            except OSError:
                pass

    def recv_dataset(self, recv_fd, dataset):
        # Defining these here instead of directly giving it in the function call
        # as that aids in readability
        force = True
        nomnt = False
        try:
            self.zfs.receive(dataset, recv_fd, force, nomnt)
        finally:
            try:
                os.close(recv_fd)
            except OSError:
                pass


class Migrate(object):
    def __init__(self, jail, _dir, pool, verbose, loop):
        self.jail = jail
        self.dir = _dir
        self.meta = f"{self.dir}/.{self.jail}.meta"
        self.pool = pool
        self.dataset = f"{self.dir}/{self.jail}"
        self.zfs = libzfs.ZFS(history=True,
                              history_prefix="<warden-migration>")
        self.ZFS = ZFS(self.pool, self.dataset, self.zfs, verbose)
        self.thread_pool_executor = ThreadPoolExecutor(2)
        self.loop = loop
        self.r_pipe, self.s_pipe = os.pipe()
        self.iocage_root = f"{self.pool}/iocage/jails/{self.jail}/root"
        self.warden_dataset = self.zfs.get_dataset_by_path(self.dataset)
        self.date = str(datetime.datetime.utcnow()).split()[0]

    async def migrate_jail(self):
        files = {
            "name": "host",
            "ip4_addr": "ipv4",
            "ip6_addr": "ipv6",
            "mac": "mac",
            "allow_props": "jail-flags",
            "warden_id": "id",
            "vnet": "vnet",
            "boot": "autostart",
            "nat": "nat",
            "defaultrouter4": "defaultrouter-ipv4",
            "defaultrouter6": "defaultrouter-ipv6"
        }

        pool_exists = self.ZFS.pool_exists()

        if not pool_exists:
            print(f"\nZFS Pool {self.pool} does not exist!\n"
                  "Please supply a valid pool for iocage usage.")
            exit(1)

        migrated = self.ZFS.jail_exists()

        if migrated:
            print(f"  {self.jail} already exists in iocage, please destroy it"
                  " first.")
            return

        iocroot = self.zfs.get_dataset(f"{self.pool}/iocage").mountpoint
        props = {}

        for ioc_prop, warden_prop in files.items():
            prop = self.jail_props(warden_prop)

            # If prop is empty, the 'prop' didn't exist in Warden
            if prop:
                if prop == "DHCP":
                    props["dhcp"] = "yes"
                    props["bpf"] = "yes"
                    props["vnet"] = "on"
                elif prop == 'AUTOCONF':
                    props['ip6_addr'] = 'accept_rtadv'
                    props['vnet'] = 'on'
                else:
                    props[ioc_prop] = prop

        self.activate_pool()
        running = self.is_jail_running()

        if running:
            print(f"  {self.jail} is running, please stop it first.")
            return

        self.create_jail(props, iocroot)

        await asyncio.gather(
            asyncio.ensure_future(self.loop.run_in_executor(
                self.thread_pool_executor,
                functools.partial(
                    self.ZFS.send_dataset,
                    self.s_pipe,
                    self.warden_dataset,
                    self.date
                )
            )),
            asyncio.ensure_future(self.loop.run_in_executor(
                self.thread_pool_executor,
                functools.partial(
                    self.ZFS.recv_dataset,
                    self.r_pipe,
                    self.iocage_root
                )
            ))
        )

        self.warden_dataset.destroy_snapshot(f"WardenMigration_{self.date}")

        if os.path.isfile(f"{self.meta}/fstab"):
            # We want to migrate their fstab
            self.copy_fstab(iocroot)
            self.fixup_fstab(iocroot)

    def is_jail_running(self):
        """
        :return: boolean if jail is running or not
        """
        cmd = ["jls", "--libxo", "json"]
        jls_json = json.loads(su.check_output(cmd))["jail-information"]["jail"]

        for jail in jls_json:
            p = f"{self.dir}/{self.jail}"
            _p = jail["path"]

            if p == _p:
                return True

        return False

    def jail_props(self, prop):
        """
        :return: the specified files contents
        """
        try:
            with open(f"{self.meta}/{prop}", "r") as p:
                _p = p.read().rstrip()

                if "allow." in _p:
                    single_period = ["allow_raw_sockets", "allow_socket_af",
                                     "allow_set_hostname"]

                    if _p in single_period:
                        _p = _p.replace(".", "_", 1).replace("true", "1")
                    else:
                        _p = _p.replace(".", "_").replace("true", "1")
                elif prop == "vnet":
                    _p = "on"
                elif prop == "autostart":
                    _p = "on"
                elif prop == "nat":
                    print("  NAT isn't supported by iocage, not migrating"
                          " property.")
        except FileNotFoundError:
            _p = ""

        return _p

    def activate_pool(self):
        su.check_call(["iocage", "activate", self.pool], stdout=su.PIPE)

    def create_jail(self, props, iocroot):
        name = props["name"]
        ip4 = props.get("ip4_addr", "none")
        ip6 = props.get("ip6_addr", "none")
        mac = props.get("mac", "none").replace(':', '')
        vnet = props.get("vnet", "off")
        warden_id = props.get("warden_id", "none")
        boot = props.get("boot", "off")
        sysctls = props.get("allow_props", "")
        release = self.get_warden_release()
        defaultrouter4 = props.get('defaultrouter4', "none")
        defaultrouter6 = props.get('defaultrouter6', "none")

        cmd = ["iocage", "create", "-n", name, "-e",
               f"notes=warden_id={warden_id}"] + sysctls.split()

        if vnet == "on":
            ip6_addr = f'vnet0|{ip6}' if ip6 != 'none' else 'none'
            ip4_addr = f'vnet0|{ip4}' if ip4 != 'none' else 'none'

            if mac != 'none':
                # Warden only uses one mac, we use two for iocage.
                mac_a = int(mac, 16)
                mac_b = mac_a + 1
                vnet0_mac = f'{mac_b:012x},{mac_a:012x}'
            else:
                vnet0_mac = 'none'

            cmd += ['vnet=on', f'ip4_addr={ip4_addr}', f'ip6_addr={ip6_addr}',
                    f'vnet0_mac={vnet0_mac}',
                    f'defaultrouter={defaultrouter4}',
                    f'defaultrouter6={defaultrouter6}']
        else:
            # iocage allows non-interface only for non-vnet
            cmd += [f'ip4_addr={ip4}', f'ip6_addr={ip6}']

        su.check_call(cmd, stdout=su.PIPE)

        with open(f'{iocroot}/jails/{name}/config.json', 'r') as config:
            config = json.load(config)

        # If we don't do this after, iocage will try to start the 'nonexistent'
        # jail.
        if boot == "on":
            config['boot'] = 'on'

        config['release'] = release

        with open(f'{iocroot}/jails/{name}/config.json', 'w') as out:
            json.dump(config, out, sort_keys=True, indent=4,
                      ensure_ascii=False)

    def copy_fstab(self, iocroot):
        try:
            os.remove(f"{iocroot}/jails/{self.jail}/fstab")
        except FileNotFoundError:
            # It should be there, but we don't care if it isn't.
            pass

        shutil.copy(f"{self.meta}/fstab", f"{iocroot}/jails/{self.jail}/fstab")

    def fixup_fstab(self, iocroot):
        with open(f"{self.meta}/fstab", 'r') as _fstab:
            with open(f"{iocroot}/jails/{self.jail}/fstab", 'w') as fstab:
                for line in _fstab:
                    line = line.replace(f'{self.dataset}/',
                                        f'{iocroot}/jails/{self.jail}/root')
                    # This needs to exist now
                    fstab_dest = line.rsplit(f'{iocroot}/jails/{self.jail}',
                                             1)[-1].split()[0]
                    destination = f'{iocroot}/jails/' \
                        f'{self.jail}/root{fstab_dest}'
                    pathlib.Path(
                        destination).mkdir(parents=True, exist_ok=True)

                    fstab.write(line)

    def get_warden_release(self):
        jail_world = su.run(['file', f'{self.dataset}/bin/sh'], stdout=su.PIPE)
        jail_world = jail_world.stdout.split()[15].decode().rstrip(',')

        return f'{jail_world}-RELEASE'


async def main(argv, loop):
    """
    :param argv: list of jails specified by -j and the iocage pool specified
    with -p
    """
    jails = []
    _dir = None
    iocage_pool = None
    verbose = False
    client = Connection()

    with client as c:
        try:
            _dir = c.call('datastore.query', 'jails.JailsConfiguration',
                          None, {'get': True})
            _dir = _dir["jc_path"]
        except ClientException:
            pass

    try:
        opts, args = getopt.getopt(argv, "vh:j:p:", ["verbose=",
                                                     "jail=",
                                                     "iocage_pool="])
    except getopt.GetoptError:
        print("migrate_warden.py <-v> -j <jail> -p <iocage-pool>")
        sys.exit(1)
    for opt, arg in opts:
        if opt == '-h':
            print("migrate_warden.py <-v> -j <jail> -p <iocage-pool>")
            sys.exit()
        elif opt in ("-j", "--jail"):
            jails.append(arg)
        elif opt in ("-p", "--iocage-pool"):
            iocage_pool = arg
        elif opt in ("-v", "--verbose"):
            verbose = True

    if len(jails) == 0:
        jails.append("ALL")

    if _dir is None:
        print("Warden does not have a path set, please set one in the GUI.")
        exit(1)

    if iocage_pool is None:
        print("Must specify the destination pool for iocage!")
        exit(1)

    _all = True if jails[0].lower() == "all" else False
    if _all:
        jails = [j for j in os.listdir(_dir) if os.path.isdir(f"{_dir}/{j}") and
                 not j.startswith(".")]

    for jail in jails:
        print(f"-- Migrating: {jail} --")
        await Migrate(jail, _dir, iocage_pool, verbose, loop).migrate_jail()


if __name__ == "__main__":
    if os.geteuid() != 0:
        sys.exit("Must be root to migrate jails!")

    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(main(sys.argv[1:], loop))
    finally:
        loop.close()

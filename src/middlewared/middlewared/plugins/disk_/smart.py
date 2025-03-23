import os
import subprocess

from middlewared.service import CallError, private, Service


class DiskService(Service):
    @private
    def smartctl(self, disk, args):
        sat = False
        if self.middleware.call_sync("system.is_enterprise"):
            if os.path.exists(f"/sys/block/{disk}/device/vpd_pg89"):
                sat = True

        # FIXME: USB disk support?

        if sat:
            args = args + ["-d", "sat"]

        p = subprocess.run(["smartctl", disk] + args, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           encoding="utf8", errors="ignore")
        if (p.returncode & 0b11) != 0:
            raise CallError(f"smartctl failed for disk {disk}:\n{p.stdout}")

        return p.stdout

    @private
    def smart_test(self, type_, disks):
        disks_map = {
            disk["identifier"]: f"/dev/{disk['name']}"
            for disk in self.middleware.call_sync("disk.query")
        }

        if "*" in disks:
            disks = list(disks_map.values())
        else:
            disks = [disks_map[disk] for disk in disks if disk in disks_map]

        errors = []
        for disk in disks:
            try:
                self.smartctl(disk, ["-t", type_.lower()])
            except Exception as e:
                errors.append(str(e))

        if errors:
            raise CallError("\n\n".join(errors))

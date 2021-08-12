# -*- coding=utf-8 -*-
import logging
import re

from middlewared.service import private, Service
from middlewared.utils import run

logger = logging.getLogger(__name__)

SKIP_REGEX = re.compile(r'Unit:\s+containerd.service')


class SystemService(Service):
    @private
    async def coredumps(self):
        coredumps = []
        coredumpctl = await run("coredumpctl", "list", "--no-pager", encoding="utf-8", errors="ignore", check=False)
        if coredumpctl.returncode != 0:
            return []

        lines = coredumpctl.stdout.splitlines()
        header = lines.pop(0)
        exe_pos = header.find("EXE")
        for line in lines:
            exe = line[exe_pos:]
            time, pid, uid, gid, sig, corefile = line[:exe_pos].rsplit(maxsplit=5)
            cp = await run("coredumpctl", "info", pid, check=False, encoding="utf-8", errors="ignore")
            if cp.returncode:
                self.logger.debug("Unable to retrieve coredump information of %r process", pid)
                continue

            if SKIP_REGEX.findall(cp.stdout):
                # We don't want to raise an alert to user about a container which died for some reason
                continue

            coredumps.append({
                "time": time,
                "pid": int(pid),
                "uid": int(uid),
                "gid": int(gid),
                "sig": int(sig),
                "corefile": corefile,
                "exe": exe,
            })
        return coredumps

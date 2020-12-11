# Copyright (c) 2019 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.
import os
import subprocess

from middlewared.service import private, Service


class EnclosureService(Service):
    @private
    def list_ses_enclosures(self):
        try:
            return [
                os.path.join("/dev/bsg", enc)
                for enc in os.listdir("/sys/class/enclosure")
            ]
        except FileNotFoundError:
            return []

    @private
    def get_ses_enclosures(self):
        output = {}
        for i, name in enumerate(self.list_ses_enclosures()):
            p = subprocess.run(["sg_ses", "--page=cf", name], encoding="utf-8", errors="ignore",
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if p.returncode != 0:
                self.middleware.logger.debug("Error querying enclosure configuration page %r: %s", name, p.stderr)
                continue
            else:
                cf = p.stdout

            p = subprocess.run(["sg_ses", "-i", "--page=es", name], encoding="utf-8", errors="ignore",
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if p.returncode != 0:
                self.middleware.logger.debug("Error querying enclosure status page %r: %s", name, p.stderr)
                continue
            else:
                es = p.stdout

            output[i] = (os.path.relpath(name, "/dev"), (cf, es))

        return output

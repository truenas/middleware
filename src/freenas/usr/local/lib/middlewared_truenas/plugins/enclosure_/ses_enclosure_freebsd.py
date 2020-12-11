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
    def get_ses_enclosures(self):
        """
        Call getencstat for all enclosures devices avaiable

        Returns:
            dict: all enclosures available with index as key
        """

        output = {}
        encnumb = 0
        while os.path.exists(f"/dev/ses{encnumb}"):
            out = self.__get_enclosure_stat(encnumb)
            if out:
                # In short, getencstat reserves the exit codes for
                # failing to change states and doesn"t actually
                # error out if it can"t read or poke at the enclosure
                # device.
                output[encnumb] = out
            encnumb += 1

        return output

    def __get_enclosure_stat(self, encnumb):
        """
        Call getencstat for single enclosures device
        """

        cmd = f"/usr/sbin/getencstat -V /dev/ses{encnumb}"
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, close_fds=True)
        # getencstat may return not valid utf8 bytes (especially on Legacy TrueNAS)
        out = p1.communicate()[0].decode("utf8", "ignore")
        return out

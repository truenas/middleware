import logging
import re

from freenasUI.common.pipesubr import pipeopen

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource

logger = logging.getLogger("FreeNASBMCAlert")


class FreeNASBMCAlertSource(ThreadedAlertSource):
    level = AlertLevel.CRITICAL
    title = "FreeNAS Mini Critical IPMI Firmware Update Available"

    onetime = True

    def check_sync(self):
        systemname = pipeopen("/usr/local/sbin/dmidecode -s system-product-name").communicate()[0].strip()
        boardname = pipeopen("/usr/local/sbin/dmidecode -s baseboard-product-name").communicate()[0].strip()
        if "freenas" in systemname.lower() and boardname == "C2750D4I":
            mcinfo = pipeopen("/usr/local/bin/ipmitool mc info").communicate()[0]
            reg = re.search(r"Firmware Revision.*: (\S+)", mcinfo, flags=re.M)
            if not reg:
                return
            fwver = reg.group(1)
            try:
                fwver = [int(i) for i in fwver.split(".")]
            except ValueError:
                logger.warning("Failed to parse BMC firmware version: {}".format(fwver))
                return

            if len(fwver) < 2 or not(fwver[0] == 0 and fwver[1] < 30):
                return

            return Alert(
                "FreeNAS Mini Critical IPMI Firmware Update - Your "
                "Mini has an available IPMI firmware update, please "
                "click <a href=\"%s\" target=\"_blank\">here</a> for "
                "installation instructions",

                "https://support.ixsystems.com/index.php?/Knowledgebase/Article/View/287"
            )

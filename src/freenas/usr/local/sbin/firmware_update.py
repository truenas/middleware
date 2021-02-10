#!/usr/bin/env python
#
# Copyright (c) 2020 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from collections import namedtuple
import logging
import logging.config
import logging.handlers
import os
from packaging import version
import re
import sys
import subprocess

SAS2FLASH = '/usr/local/sbin/sas2flash'
SAS3FLASH = '/usr/local/sbin/sas3flash'
STORCLI = '/usr/local/sbin/storcli'
FWPATH = '/usr/local/share/firmware/'
FAILED_UPDATE_SENTINEL = '/data/.hba_firmware_update_fail'
UPDATE_SENTINEL = '/data/.hba_firmware_update'

UPDATE_SUCCESS = []
UPDATE_FAIL = []

Firmware = namedtuple("Firmware", ["path", "version"])


def get_firmware(prefix):
    for item in os.listdir(FWPATH):
        if item.startswith(prefix):
            if m := re.match(r".+\.([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)\.bin$", item):
                return Firmware(os.path.join(FWPATH, item), version.parse(m.group(1)))

    logger.error("Unable to find firmware file with prefix %r", prefix)
    return None


logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'datetime': {
            'format': '%(asctime)s %(message)s',
        },
    },
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'formatter': 'datetime',
            'level': 'DEBUG',
            'filename': '/data/hba_firmware_update.log',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'stream': 'ext://sys.stdout',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
})
logger = logging.getLogger(__name__)

if os.path.exists(FAILED_UPDATE_SENTINEL):
    # Prevent a firmware flash failure from causing a boot loop
    logger.info("Failure sentinel present, skipping HBA firmware checks")
    sys.exit(255)


logger.info("Checking SAS92xx HBAs firmware")
proc = subprocess.Popen([
    SAS2FLASH, "-listall"
], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
listall = proc.communicate()[0].decode("utf8", "ignore").strip()
# logger.debug(listall)

for hba in re.finditer(r"^(([0-9]+) +[^ ]+ +([0-9]{2}\.[0-9]{2}\.[0-9]{2}\.[0-9]{2}) +.*)$", listall, re.MULTILINE):
    logger.debug(hba.group(1))
    n = hba.group(2)
    controller = "SAS92xx#%s" % n
    firmware_version = version.parse(hba.group(3))
    if firmware_version < version.parse("1"):
        logger.error("Can't get firmware version")
        continue

    proc = subprocess.Popen([
        SAS2FLASH, "-list", "-c", n
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    info = proc.communicate()[0].decode("utf8", "ignore").strip()
    m = re.search(r"Board Name *: *([^ ]+)$", info, re.MULTILINE)
    if m is None:
        logger.error("Can't get board name")
        logger.debug(info)
        continue
    boardname = m.group(1)
    # In some cases we'll end up with a board name like:
    # SAS9206-16E (Notice the ending E is capitalized...)
    if boardname.endswith("E"):
        boardname = boardname[:-1] + 'e'
    if boardname.endswith("I"):
        boardname = boardname[:-1] + 'i'
    logger.debug("Board Name is %s" % boardname)

    new_firmware = get_firmware(f"mps_{boardname}")
    if not new_firmware:
        continue
    bios_file = os.path.join(FWPATH, "mps_bios.rom")
    if not os.path.exists(bios_file):
        logger.error("BIOS image %s not found" % bios_file)
        continue

    if firmware_version >= new_firmware.version:
        logger.debug("Up to date firmware version %r" % firmware_version)
        continue
    logger.info("Found old firmware %r, updating to %r" % (firmware_version, new_firmware.version))

    ret = subprocess.run([SAS2FLASH, "-c", n, "-b", bios_file, "-f", new_firmware.path])
    if not ret.returncode:
        logger.info("Update successful")
        UPDATE_SUCCESS.append(controller)
    else:
        logger.error("Update failed: %s -c %s -b %s -f %s returned %d" %
                     (SAS2FLASH, n, bios_file, new_firmware.path, ret.returncode))
        UPDATE_FAIL.append(controller)

logger.debug("")


logger.info("Checking SAS93xx HBAs firmware")
proc = subprocess.Popen([
    SAS3FLASH, "-listall"
], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
listall = proc.communicate()[0].decode("utf8", "ignore").strip()
# logger.debug(listall)

for hba in re.finditer(r"^(([0-9]+) +[^ ]+ +([0-9]{2}\.[0-9]{2}\.[0-9]{2}\.[0-9]{2}) +.*)$", listall, re.MULTILINE):
    logger.debug(hba.group(1))
    n = hba.group(2)
    controller = "SAS93xx#%s" % n
    firmware_version = version.parse(hba.group(3))
    if firmware_version < version.parse("1"):
        logger.error("Can't get firmware version")
        continue

    proc = subprocess.Popen([
        SAS3FLASH, "-list", "-c", n
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    info = proc.communicate()[0].decode("utf8", "ignore").strip()
    m = re.search(r"Board Name *: *([^ ]+)$", info, re.MULTILINE)
    if m is None:
        logger.error("Can't get board name")
        logger.debug(info)
        continue
    boardname = m.group(1)
    # Echostreams HBAs have different PCBs, but use standard firmware.
    if boardname == "Echostreams HBA":
        boardname = "SAS9300-8i"
    logger.debug("Board Name is %s" % boardname)

    new_firmware = get_firmware(f"mpr_{boardname}")
    if not new_firmware:
        continue
    bios_file = os.path.join(FWPATH, "mpr_bios.rom")
    if not os.path.exists(bios_file):
        logger.error("BIOS image %s not found" % bios_file)
        continue

    if firmware_version >= new_firmware.version:
        logger.debug("Up to date firmware version %d" % firmware_version)
        continue
    logger.info("Found old firmware %r, updating to %r" % (firmware_version, new_firmware.version))

    ret = subprocess.run([SAS3FLASH, "-c", n, "-b", bios_file, "-f", new_firmware.path])
    if not ret.returncode:
        logger.info("Update successful")
        UPDATE_SUCCESS.append(controller)
    else:
        logger.error("Update failed: %s -c %s -b %s -f %s returned %d" %
                     (SAS3FLASH, n, bios_file, new_firmware.path, ret.returncode))
        UPDATE_FAIL.append(controller)

logger.debug("")


logger.info("Checking HBA94xx HBAs firmware")
proc = subprocess.Popen([
    STORCLI, "show"
], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
listall = proc.communicate()[0].decode("utf8", "ignore").strip()
# logger.debug(listall)

for hba in re.finditer(r"^( *([0-9]+) +(HBA 94[^ ]+) +SAS.*)$", listall, re.MULTILINE):
    logger.debug(hba.group(1))
    n = hba.group(2)
    controller = "HBA94xx#%s" % n
    boardname = hba.group(3).replace(" ", "")
    logger.debug("Board Name is %s" % boardname)

    proc = subprocess.Popen([
        STORCLI, "/c%s" % n, "show"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    info = proc.communicate()[0].decode("utf8", "ignore").strip()
    m = re.search(r"^FW Version = ([0-9]{2}\.[0-9]{2}\.[0-9]{2}\.[0-9]{2})$", info, re.MULTILINE)
    if m is None:
        logger.error("Can't get firmware version")
        logger.debug(info)
        continue
    firmware_version = version.parse(m.group(1))
    if firmware_version < version.parse("1"):
        logger.error("Can't get firmware version")
        logger.debug(info)
        continue

    new_firmware = get_firmware(f"mpr_{boardname}")
    if not new_firmware:
        continue
    efibios_file = os.path.join(FWPATH, "mpr_HBA_efibios.rom")
    if not os.path.exists(efibios_file):
        logger.error("EFI BIOS image %s not found" % efibios_file)
        continue

    if firmware_version >= new_firmware.version:
        logger.debug("Up to date firmware version %d" % firmware_version)
        continue
    logger.info("Found old firmware %r, updating to %r" % (firmware_version, new_firmware.version))

    ret = subprocess.run([STORCLI, "/c%s" % n, "download", "file=" + new_firmware.path])
    if not ret.returncode:
        logger.info("Update successful")
        UPDATE_SUCCESS.append(controller)
    else:
        logger.error("Update failed: %s /c%s download file=%s returned %d" %
                     (STORCLI, n, new_firmware.path, ret.returncode))
        UPDATE_FAIL.append(controller)
        continue

    ret = subprocess.run([STORCLI, "/c%s" % n, "download", "efibios", "file=" + efibios_file])
    if not ret.returncode:
        logger.info("EFI BIOS update successful")
    else:
        logger.error("Update failed: %s /c%s download efibios file=%s returned %d" %
                     (STORCLI, n, efibios_file, ret.returncode))

logger.debug("")
logger.info("HBA firmware check complete")
logger.debug("")


if len(UPDATE_FAIL) > 0:
    fh = open(FAILED_UPDATE_SENTINEL, "w")
    fh.write(', '.join(UPDATE_FAIL))
    fh.close()

if os.path.exists(UPDATE_SENTINEL):
    os.unlink(UPDATE_SENTINEL)

if len(UPDATE_SUCCESS) > 0:
    # signal our caller a reboot is needed with a return value of 0
    sys.exit(0)
if len(UPDATE_SUCCESS) == 0 and len(UPDATE_FAIL) == 0:
    # There were no controllers that needed updating
    sys.exit(254)
if len(UPDATE_FAIL) > 0:
    # The caller doesn't do anything with non-zero return codes as of right now
    sys.exit(len(UPDATE_FAIL))

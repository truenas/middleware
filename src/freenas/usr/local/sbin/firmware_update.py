#!/usr/bin/env python
#
# Copyright (c) 2020 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import os
import re
import sys
import subprocess

SAS2FLASH = '/usr/local/sbin/sas2flash'
SAS3FLASH = '/usr/local/sbin/sas3flash'
STORCLI = '/usr/local/sbin/storcli'
FWPATH = '/usr/local/share/firmware/'
FAILED_UPDATE_SENTINEL = '/data/.hba_fimware_flash_fail'
UPDATE_SENTINEL = '/data/.hba_firmware_update'
LOGFILE = '/data/hba_firmware_flash.log'
LOGLINES = []

SAS92_VERSION = 20
SAS93_VERSION = 16
HBA94_VERSION = 13

UPDATE_SUCCESS = []
UPDATE_FAIL = []

if os.path.exists(FAILED_UPDATE_SENTINEL):
    # Prevent a firmware flash failure from causing a boot loop
    LOGLINES.append("Failure sentinel present, bailing out now")
    fh = open(LOGFILE, "w")
    for line in LOGLINES:
        fh.write(line)
    fh.close()
    sys.exit(255)


LOGLINES.append("Checking SAS92xx HBAs")
proc = subprocess.Popen([
    SAS2FLASH, "-listall"
], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
listall = proc.communicate()[0].decode("utf8", "ignore").strip()
# LOGLINES.append(listall)

for hba in re.finditer(r"^(([0-9]+) +[^ ]+ +([0-9]{2})\.[0-9]{2}\.[0-9]{2}\.[0-9]{2} +.*)$", listall, re.MULTILINE):
    LOGLINES.append(hba.group(1))
    n = hba.group(2)
    controller = "SAS92xx#%s" % n
    firmware_version = int(hba.group(3))
    if firmware_version < 1:
        LOGLINES.append("Can't get firmware version")
        continue
    if firmware_version >= SAS92_VERSION:
        LOGLINES.append("Up to date firmware version %d" % firmware_version)
        continue
    LOGLINES.append("Old firmware version %d, updating to %d" % (firmware_version, SAS92_VERSION))

    proc = subprocess.Popen([
        SAS2FLASH, "-list", "-c", n
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    info = proc.communicate()[0].decode("utf8", "ignore").strip()
    m = re.search(r"Board Name *: *([^ ]+)$", info, re.MULTILINE)
    if m is None:
        LOGLINES.append("Can't get board name")
        LOGLINES.append(info)
        continue
    boardname = m.group(1)
    # In some cases we'll end up with a board name like:
    # SAS9206-16E (Notice the ending E is capitalized...)
    if boardname.endswith("E"):
        boardname = boardname[:-1] + 'e'
    if boardname.endswith("I"):
        boardname = boardname[:-1] + 'i'
    LOGLINES.append("Board Name is %s" % boardname)

    firmware_file = "%smps_%s_p%s.firmware.bin" % (FWPATH, boardname, SAS92_VERSION)
    if not os.path.exists(firmware_file):
        LOGLINES.append("Firmware image %s not found" % firmware_file)
        continue
    bios_file = "%smps_p%s_bios.rom" % (FWPATH, SAS92_VERSION)
    if not os.path.exists(bios_file):
        LOGLINES.append("BIOS image %s not found" % bios_file)
        continue

    ret = subprocess.run([SAS2FLASH, "-c", n, "-b", bios_file, "-f", firmware_file])
    if not ret.returncode:
        LOGLINES.append("Update successful")
        UPDATE_SUCCESS.append(controller)
    else:
        LOGLINES.append("%s -c %s -b %s -f %s returned %d" %
                        (SAS2FLASH, n, bios_file, firmware_file, ret.returncode))
        UPDATE_FAIL.append(controller)

LOGLINES.append("")


LOGLINES.append("Checking SAS93xx HBAs")
proc = subprocess.Popen([
    SAS3FLASH, "-listall"
], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
listall = proc.communicate()[0].decode("utf8", "ignore").strip()
# LOGLINES.append(listall)

for hba in re.finditer(r"^(([0-9]+) +[^ ]+ +([0-9]{2})\.[0-9]{2}\.[0-9]{2}\.[0-9]{2} +.*)$", listall, re.MULTILINE):
    LOGLINES.append(hba.group(1))
    n = hba.group(2)
    controller = "SAS93xx#%s" % n
    firmware_version = int(hba.group(3))
    if firmware_version < 1:
        LOGLINES.append("Can't get firmware version")
        continue
    if firmware_version >= SAS93_VERSION:
        LOGLINES.append("Up to date firmware version %d" % firmware_version)
        continue
    LOGLINES.append("Old firmware version %d, updating to %d" % (firmware_version, SAS93_VERSION))

    proc = subprocess.Popen([
        SAS3FLASH, "-list", "-c", n
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    info = proc.communicate()[0].decode("utf8", "ignore").strip()
    m = re.search(r"Board Name *: *([^ ]+)$", info, re.MULTILINE)
    if m is None:
        LOGLINES.append("Can't get board name")
        LOGLINES.append(info)
        continue
    boardname = m.group(1)
    # Echostreams HBAs have different PCBs, but use standard firmware.
    if boardname == "Echostreams HBA":
        boardname = "SAS9300-8i"
    LOGLINES.append("Board Name is %s" % boardname)

    firmware_file = "%smpr_%s_p%s.firmware.bin" % (FWPATH, boardname, SAS93_VERSION)
    if not os.path.exists(firmware_file):
        LOGLINES.append("Firmware image %s not found" % firmware_file)
        continue
    bios_file = "%smpr_p%s_bios.rom" % (FWPATH, SAS93_VERSION)
    if not os.path.exists(bios_file):
        LOGLINES.append("BIOS image %s not found" % bios_file)
        continue

    ret = subprocess.run([SAS3FLASH, "-c", n, "-b", bios_file, "-f", firmware_file])
    if not ret.returncode:
        LOGLINES.append("Update successful")
        UPDATE_SUCCESS.append(controller)
    else:
        LOGLINES.append("%s -c %s -b %s -f %s returned %d" %
                        (SAS3FLASH, n, bios_file, firmware_file, ret.returncode))
        UPDATE_FAIL.append(controller)

LOGLINES.append("")


LOGLINES.append("Checking HBA94xx HBAs")
proc = subprocess.Popen([
    STORCLI, "show"
], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
listall = proc.communicate()[0].decode("utf8", "ignore").strip()
# LOGLINES.append(listall)

for hba in re.finditer(r"^( *([0-9]+) +(HBA 94[^ ]+) +SAS.*)$", listall, re.MULTILINE):
    LOGLINES.append(hba.group(1))
    n = hba.group(2)
    controller = "HBA94xx#%s" % n
    boardname = hba.group(3).replace(" ", "")
    LOGLINES.append("Board Name is %s" % boardname)

    proc = subprocess.Popen([
        STORCLI, "/c%s" % n, "show"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    info = proc.communicate()[0].decode("utf8", "ignore").strip()
    m = re.search(r"^FW Version = ([0-9]{2})\.[0-9]{2}\.[0-9]{2}\.[0-9]{2}$", info, re.MULTILINE)
    if m is None:
        LOGLINES.append("Can't get firmware version")
        LOGLINES.append(info)
        continue
    firmware_version = int(m.group(1))
    if firmware_version < 1:
        LOGLINES.append("Can't get firmware version")
        continue
    if firmware_version >= HBA94_VERSION:
        LOGLINES.append("Up to date firmware version %d" % firmware_version)
        continue
    LOGLINES.append("Old firmware version %d, updating to %d" % (firmware_version, HBA94_VERSION))

    firmware_file = "%smpr_%s_p%s.firmware.bin" % (FWPATH, boardname, HBA94_VERSION)
    if not os.path.exists(firmware_file):
        LOGLINES.append("Firmware image %s not found" % firmware_file)
        continue
    efibios_file = "%smpr_HBA_p%s_efibios.rom" % (FWPATH, HBA94_VERSION)
    if not os.path.exists(efibios_file):
        LOGLINES.append("EFI BIOS image %s not found" % efibios_file)
        continue

    ret = subprocess.run([STORCLI, "/c%s" % n, "download", "file=" + firmware_file])
    if not ret.returncode:
        LOGLINES.append("Update successful")
        UPDATE_SUCCESS.append(controller)
    else:
        LOGLINES.append("%s /c%s download file=%s returned %d" %
                        (STORCLI, n, firmware_file, ret.returncode))
        UPDATE_FAIL.append(controller)
        continue

    ret = subprocess.run([STORCLI, "/c%s" % n, "download", "efibios", "file=" + efibios_file])
    if not ret.returncode:
        LOGLINES.append("EFI BIOS update successful")
    else:
        LOGLINES.append("%s /c%s download efibios file=%s returned %d" %
                        (STORCLI, n, efibios_file, ret.returncode))


if len(UPDATE_FAIL) > 0:
    fh = open(FAILED_UPDATE_SENTINEL, "w")
    fh.write(', '.join(UPDATE_FAIL))
    fh.close()

if LOGLINES:
    fh = open(LOGFILE, "w")
    for line in LOGLINES:
        fh.write(line)
        fh.write("\n")
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

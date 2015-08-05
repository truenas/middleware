#!/usr/bin/env python
#+
# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import os
import sys

SAS3FLASH = '/usr/local/sbin/sas3flash'
SAS2FLASH = '/usr/local/sbin/sas2flash'
FAILED_UPDATE_SENTINEL = '/data/.hba_fimware_flash_fail'

MPS_VERSION = '16'
MPR_VERSION = '9'

UPDATE_SUCCESS = []
UPDATE_FAIL = []

if os.path.exists(FAILED_UPDATE_SENTINEL):
    # Prevent a firmware flash failure from causing a boot loop
    sys.exit(255)

dirlist = os.listdir("/dev/")
controllerlist = [x for x in dirlist if x.startswith("mpr") or x.startswith("mps")]
for controller in controllerlist:
    if controller.startswith("mps"):
        controller_number = controller[3:]
        controller_output = os.popen('%s -list -c %' % (SAS2FLASH, controller_number)).readlines()
        controller_output_cooked = [x.replace('\t', '').replace('\n', '') for x in controller_output]
        for line in controller_output_cooked:
            if line.startswith("Board Name"):
                # Board Name                     : SAS9200-8e
                controller_boardname = line.split(":")[1].lstrip().strip()
                # SAS9200-8e
            if line.startswith("Firmware Version"):
                # Firmware Version               : 16.01.00.00
                controller_firmware_version = int(line.split(":")[1].lstrip().strip().split(".")[0])
                # 16
        if MPS_VERSION > controller_firmware_version:
            firmware_file = "/usr/local/share/firmware/mps_%s_p%s.firmware.bin" % \
                (controller_boardname, MPS_VERSION)
            bios_file = "/usr/local/share/firmware/mps_p%s_bios.rom" % MPS_VERSION
            if os.path.exists(firmware_file) and os.path.exists(bios_file):
                ret = os.system("%s -c %s -b %s -f %s" %
                                (SAS2FLASH, controller_number,
                                 bios_file, firmware_file))
                if not ret:
                    UPDATE_SUCCESS.append(controller)
                else:
                    UPDATE_FAIL.append(controller)
            else:
                UPDATE_FAIL.append(controller)
    if controller.startswith("mpr"):
        controller_number = controller[3:]
        controller_output = os.popen('%s -list -c %' % (SAS3FLASH, controller_number)).readlines()
        controller_output_cooked = [x.replace('\t', '').replace('\n', '') for x in controller_output]
        for line in controller_output_cooked:
            if line.startswith("Board Name"):
                # Board Name                     : SAS9300-4i4e
                controller_boardname = line.split(":")[1].lstrip().strip()
                # SAS9300-4i4e
            if line.startswith("Firmware Version"):
                # Firmware Version               : 09.00.00.00
                controller_firmware_version = int(line.split(":")[1].lstrip().strip().split(".")[0])
                # 9
        if MPR_VERSION > controller_firmware_version:
            firmware_file = "/usr/local/share/firmware/mpr_%s_p%s.firmware.bin" % \
                (controller_boardname, MPR_VERSION)
            bios_file = "/usr/local/share/firmware/mpr_p%s_bios.rom" % MPR_VERSION
            if os.path.exists(firmware_file) and os.path.exists(bios_file):
                ret = os.system("%s -c %s -b %s -f %s" %
                                (SAS3FLASH, controller_number,
                                 bios_file, firmware_file))
                if not ret:
                    UPDATE_SUCCESS.append(controller)
                else:
                    UPDATE_FAIL.append(controller)
            else:
                UPDATE_FAIL.append(controller)

if len(UPDATE_FAIL) > 0:
    fh = open(FAILED_UPDATE_SENTINEL, "w")
    fh.write(UPDATE_FAIL)
    fh.close()

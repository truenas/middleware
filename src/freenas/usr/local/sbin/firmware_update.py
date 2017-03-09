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
UPDATE_SENTINEL = '/data/.hba_firmware_update'
LOGFILE = '/data/hba_firmware_flash.log'
LOGLINES = []

MPS_VERSION = 20
MPR_VERSION = 14

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

dirlist = os.listdir("/dev/")
controllerlist = [x for x in dirlist if x.startswith("mpr") or x.startswith("mps")]
for controller in controllerlist:
    # Iterate over /dev/mprX and /dev/mpsX, use sas2flash or sas3flash a
    # appropriate to get the exact board model and it's current firmware
    # version.  If the firmware version major number doesn't match
    # MP[R|S]_VERSION use sas[2|3]flash to flash the card with the
    # firmware contained in the image.  We include some anti-downgrade logic
    # because sas[2|3]flash can't downgrade firmware without additional magic.
    # This code can't handle minor version upgrades, but since that has never
    # been neccesary previously we'll cross that bridge when we get to it.
    if controller.startswith("mpr"):
        controller_number = controller[3:]
        try:
            controller_output = os.popen('%s -list -c %s' %
                                         (SAS3FLASH, controller_number)).readlines()
        except OSError:
            LOGLINES.append("An error was encountered running %s -list -c %s" %
                            (SAS3FLASH, controller_number))
            if controller_output:
                LOGLINES.append(controller_output)
            UPDATE_FAIL.append(controller)
            continue
        controller_output_cooked = [x.replace('\t', '').replace('\n', '')
                                    for x in controller_output]
        if len(controller_output_cooked) < 5:
            # We should have at a minimum a few dozen lines at this point, 5
            # is an arbitrary number of lines to test for that means
            # something is drastically wrong, so we'll just bail out
            # here and mark the update of this controller as failed,
            # because things will certainly fail down the line
            LOGLINES.append("Aborting firmware update on %s"
                            "due to sas3flash output being too short" % controller)
            if controller_output_cooked:
                for line in controller_output_cooked:
                    LOGLINES.append(line)
            UPDATE_FAIL.append(controller)
            continue
        controller_boardname = None
        controller_firmware_version = None
        for line in controller_output_cooked:
            if line.startswith("Board Name"):
                # We should have a line like:
                # Board Name                     : SAS9300-8e
                try:
                    # All sorts of reasons this might not work, we won't attempt
                    # to figure out what went wrong, we'll just give up trying
                    # to do anything automagically
                    controller_boardname = line.split(":")[1].lstrip().strip()
                except:
                    LOGLINES.append("Determining boardname for %s failed." % controller)
                    if controller_boardname:
                        LOGLINES.append(controller_boardname)
                    else:
                        LOGLINES.append(line)
                    UPDATE_FAIL.append(controller)
                    continue
                # If all is well we'll end up with the
                # following in controller_boardname:
                # SAS9200-8e
                try:
                    # If the boardname doesn't start with SAS we aren't
                    # going to have a firmware for it anyways.
                    # This should never happen on TrueNAS BOM hardware
                    assert controller_boardname.startswith("SAS")
                except:
                    LOGLINES.append("Invalid boardname detected for %s" % controller)
                    if controller_boardname:
                        LOGLINES.append(controller_boardname)
                    UPDATE_FAIL.append(controller)
                    continue

                # In some cases we'll end up with a board name like:
                # SAS9300-16E (Notice the ending E is capitalized...)
                # Handle that case by cooking the output
                # If we don't do this we'll ultimately fail because the
                # firmware files are all mps_SAS9206-16e_p20.firmware.bin
                # Notice the mixed case...I did that so I couldn't
                # just use lower()...sigh
                if controller_boardname.endswith("E"):
                    controller_boardname = controller_boardname[:-1] + 'e'
                if controller_boardname.endswith("I"):
                    controller_boardname = controller_boardname[:-1] + 'i'

            if line.startswith("Firmware Version"):
                # We should have a line like:
                # Firmware Version               : 09.00.00.00
                try:
                    # All sorts of reasons this might not work, we won't attempt
                    # to figure out what went wrong, we'll just give up trying
                    # to do anything automagically
                    controller_firmware_version = \
                        int(line.split(":")[1].lstrip().strip().split(".")[0])
                except:
                    LOGLINES.append("Determining firmware version on %s failed." % controller)
                    if controller_firmware_version:
                        LOGLINES.append(controller_firmware_version)
                    else:
                        LOGLINES.append(line)
                    UPDATE_FAIL.append(controller)
                    continue
                # If all is well we'll end up with the
                # following in controller_firmware_version:
                # 16
                try:
                    # If we don't have a positive integer at this point
                    # something went drastically wrong.
                    assert controller_firmware_version > 0
                except:
                    LOGLINES.append("assert controller_firmware_version > 0"
                                    "failed for %s" % controller)
                    if controller_firmware_version:
                        LOGLINES.append(controller_firmware_version)
                    UPDATE_FAIL.append(controller)
                    continue
        try:
            assert controller_boardname is not None and controller_firmware_version is not None
        except AssertionError:
            LOGLINES.append("Unable to determine boardname or firmware version for %s" % controller)
            LOGLINES.append("boardname: %s firmware version: %s" %
                            (controller_boardname, controller_firmware_version))
        # anti-downgrade logic
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
                    LOGLINES.append("%s -c %s -b %s -f %s failed for %s" %
                                    (SAS3FLASH, controller_number,
                                     bios_file, firmware_file, controller))
                    UPDATE_FAIL.append(controller)
            else:
                # We got here because either the firmware file or the bios file
                # (or both!) doesn't exist.
                if not os.path.exists(firmware_file):
                    LOGLINES.append("%s for %s not found" % (firmware_file, controller))
                if not os.path.exists(bios_file):
                    LOGLINES.append("%s for %s not found" % (bios_file, controller))
                UPDATE_FAIL.append(controller)

    if controller.startswith("mps"):
        controller_number = controller[3:]
        try:
            controller_output = os.popen('%s -list -c %s' %
                                         (SAS2FLASH, controller_number)).readlines()
        except OSError:
            LOGLINES.append("An error was encountered running %s -list -c %s" %
                            (SAS2FLASH, controller_number))
            if controller_output:
                LOGLINES.append(controller_output)
            UPDATE_FAIL.append(controller)
            continue
        controller_output_cooked = [x.replace('\t', '').replace('\n', '')
                                    for x in controller_output]
        if len(controller_output_cooked) < 5:
            # We should have at a minimum a few dozen lines at this point, 5
            # is an arbitrary number of lines to test for that means
            # something is drastically wrong, so we'll just bail out
            # here and mark the update of this controller as failed,
            # because things will certainly fail down the line
            LOGLINES.append("Aborting firmware update on %s"
                            "due to sas2flash output being too short" % controller)
            if controller_output_cooked:
                for line in controller_output_cooked:
                    LOGLINES.append(line)
            UPDATE_FAIL.append(controller)
            continue
        controller_boardname = None
        controller_firmware_version = None
        for line in controller_output_cooked:
            if line.startswith("Board Name"):
                # We should have a line like:
                # Board Name                     : SAS9200-8e
                try:
                    # All sorts of reasons this might not work, we won't attempt
                    # to figure out what went wrong, we'll just give up trying
                    # to do anything automagically
                    controller_boardname = line.split(":")[1].lstrip().strip()
                except:
                    LOGLINES.append("Determining boardname for %s failed." % controller)
                    if controller_boardname:
                        LOGLINES.append(controller_boardname)
                    else:
                        LOGLINES.append(line)
                    UPDATE_FAIL.append(controller)
                    continue
                # If all is well we'll end up with the
                # following in controller_boardname:
                # SAS9200-8e
                try:
                    # If the boardname doesn't start with SAS we aren't
                    # going to have a firmware for it anyways.
                    # This should never happen on TrueNAS BOM hardware
                    assert (controller_boardname.startswith("SAS") or
                            controller_boardname.startswith("SMC") or
                            controller_boardname.startswith("LSI"))
                except:
                    LOGLINES.append("Invalid boardname detected for %s" % controller)
                    if controller_boardname:
                        LOGLINES.append(controller_boardname)
                    UPDATE_FAIL.append(controller)
                    continue

                # In some cases we'll end up with a board name like:
                # SAS9206-16E (Notice the ending E is capitalized...)
                # Handle that case by cooking the output
                # If we don't do this we'll ultimately fail because the
                # firmware files are all mps_SAS9206-16e_p20.firmware.bin
                # Notice the mixed case...I did that so I couldn't
                # just use lower()...sigh
                if controller_boardname.endswith("E"):
                    controller_boardname = controller_boardname[:-1] + 'e'
                if controller_boardname.endswith("I"):
                    controller_boardname = controller_boardname[:-1] + 'i'

            if line.startswith("Firmware Version"):
                # We should have a line like:
                # Firmware Version               : 16.00.01.00
                try:
                    # All sorts of reasons this might not work, we won't attempt
                    # to figure out what went wrong, we'll just give up trying
                    # to do anything automagically
                    controller_firmware_version = \
                        int(line.split(":")[1].lstrip().strip().split(".")[0])
                except:
                    LOGLINES.append("Determining firmware version on %s failed." % controller)
                    if controller_firmware_version:
                        LOGLINES.append(controller_firmware_version)
                    else:
                        LOGLINES.append(line)
                    UPDATE_FAIL.append(controller)
                    continue
                # If all is well we'll end up with the
                # following in controller_firmware_version:
                # 16
                try:
                    # If we don't have a positive integer at this point
                    # something went drastically wrong.
                    assert controller_firmware_version > 0
                except:
                    LOGLINES.append("assert controller_firmware_version > 0"
                                    "failed for %s" % controller)
                    if controller_firmware_version:
                        LOGLINES.append(controller_firmware_version)
                    UPDATE_FAIL.append(controller)
                    continue
        try:
            assert controller_boardname is not None and controller_firmware_version is not None
        except AssertionError:
            LOGLINES.append("Unable to determine boardname or firmware version for %s" % controller)
            LOGLINES.append("boardname: %s firmware version: %s" %
                            (controller_boardname, controller_firmware_version))
        # anti-downgrade logic
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
                    LOGLINES.append("%s -c %s -b %s -f %s failed for %s" %
                                    (SAS2FLASH, controller_number,
                                     bios_file, firmware_file, controller))
                    UPDATE_FAIL.append(controller)
            else:
                # We got here because either the firmware file or the bios file
                # (or both!) doesn't exist.
                if not os.path.exists(firmware_file):
                    LOGLINES.append("%s for %s not found" % (firmware_file, controller))
                if not os.path.exists(bios_file):
                    LOGLINES.append("%s for %s not found" % (bios_file, controller))
                UPDATE_FAIL.append(controller)

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

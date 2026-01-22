# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions
from enum import StrEnum

__all__ = ("DisabledReasonsEnum",)


class DisabledReasonsEnum(StrEnum):
    NO_CRITICAL_INTERFACES = "No network interfaces are marked critical for failover."
    MISMATCH_DISKS = "The quantity of disks do not match between the nodes."
    MISMATCH_VERSIONS = (
        "TrueNAS software versions do not match between storage controllers."
    )
    MISMATCH_NICS = "Network interfaces do not match between storage controllers."
    DISAGREE_VIP = "Nodes Virtual IP states do not agree."
    NO_LICENSE = "Other node has no license."
    NO_FAILOVER = "Administratively Disabled."
    NO_PONG = "Unable to contact remote node via the heartbeat interface."
    NO_VOLUME = "No zpools have been configured or the existing zpool couldn't be imported."
    NO_VIP = "No interfaces have been configured with a Virtual IP."
    NO_SYSTEM_READY = "Other node has not finished booting."
    NO_FENCED = "Fenced is not running."
    REM_FAILOVER_ONGOING = "Other node is currently processing a failover event."
    LOC_FAILOVER_ONGOING = "This node is currently processing a failover event."
    NO_HEARTBEAT_IFACE = "Local heartbeat interface does not exist."
    NO_CARRIER_ON_HEARTBEAT = "Local heartbeat interface is down."
    LOC_FIPS_REBOOT_REQ = "This node needs to be rebooted to apply FIPS configuration"
    REM_FIPS_REBOOT_REQ = "Other node needs to be rebooted to apply FIPS configuration"
    LOC_GPOSSTIG_REBOOT_REQ = "This node needs to be rebooted to apply GPOS configuration"
    REM_GPOSSTIG_REBOOT_REQ = "Other node needs to be rebooted to apply GPOS configuration"
    LOC_UPGRADE_REBOOT_REQ = "This node needs to be rebooted to complete the system upgrade"
    REM_UPGRADE_REBOOT_REQ = "Other node needs to be rebooted to complete the system upgrade"
    LOC_SYSTEM_DATASET_MIGRATION_IN_PROGRESS = (
        "This node is currently configuring the system dataset"
    )
    REM_SYSTEM_DATASET_MIGRATION_IN_PROGRESS = (
        "Other node is currently configuring the system dataset"
    )

import re

SYSFS_SLOT_KEY = "sysfs_slot"
MAPPED_SLOT_KEY = "mapped_slot"
SUPPORTS_IDENTIFY_KEY = "supports_identify_light"
SUPPORTS_IDENTIFY_STATUS_KEY = "supports_identify_light_status"
DRIVE_BAY_LIGHT_STATUS = "drive_bay_light_status"
MINI_MODEL_BASE = "MINI"
MINIR_MODEL_BASE = f"{MINI_MODEL_BASE}-R"
HEAD_UNIT_DISK_SLOT_START_NUMBER = 1
DISK_FRONT_KEY = "is_front"
DISK_REAR_KEY = "is_rear"
DISK_TOP_KEY = "is_top"
DISK_INTERNAL_KEY = "is_internal"

# These are suffixes that get added on to the end
# of models that we flash in DMI for the various
# platforms we sell. We must remove them when we
# enumerate enclosures and friends so model/platform
# detection is done properly.
# NOTE: "-PC", "-SC", and "-C" are used on R60 platform
DMI_SUFFIXES_TO_REMOVE = ("-HA", "-S", "-PC", "-SC", "-C")

# SES Array Device Slot element type code (SES-4 7.1, Table 71 -- element type
# codes). Numeric counterpart of enums.ElementType.ARRAY_DEVICE_SLOT.
ARRAY_DEVICE_SLOT_ELEMENT_TYPE = 23

# V-series enclosure products as reported by SES INQUIRY (bare product string,
# no vendor prefix). V2xx (V260/V280) front bays are served by a PEX89088 PCIe
# switch partitioned into two VirtualSES enclosures; all V-series rear bays are
# served by the bifurcated PEX89032 NTB/NTG chip.
VSERIES_FRONT_PRODUCTS = ("4IXGA-SWp", "4IXGA-SWs")
VSERIES_REAR_PRODUCTS = ("4IXGA-NTBp", "4IXGA-NTBs", "4IXGA-NTGp", "4IXGA-NTGs")

# Matches an SES Array Device Slot element descriptor like "slot01".."slot24".
# V-series VirtualSES enclosures use these labels to advertise the slots a
# partition owns; slots it does not own are reported with descriptor "<empty>".
SLOT_DESCRIPTOR_RE = re.compile(r"^slot(\d+)$")

# Matches an NVMe namespace block device name like "nvme7n1".
NVME_NAMESPACE_RE = re.compile(r"nvme\d+n\d+")

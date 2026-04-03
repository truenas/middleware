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

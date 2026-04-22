import enum


class ISCSIMODE(enum.IntEnum):
    SCST_DLM_PRSTATE_SAVE = 0
    SCST_DLM_PRSTATE_NOSAVE = 1
    LIO = 2


class ALUA_STATE(enum.IntEnum):
    """Values match ASYMMETRIC ACCESS STATE table in SPC-5"""

    OPTIMIZED = 0
    NONOPTIMIZED = 1
    STANDBY = 2
    UNAVAILABLE = 3
    OFFLINE = 14
    TRANSITIONING = 15

    def __str__(self):
        return str(self.value)


# HA ALUA target port group names and IDs (must match SCST scst.conf.mako hardcoding)
ALUA_GROUP_A = "controller_A"
ALUA_GROUP_B = "controller_B"
ALUA_GROUP_ID_A = 101
ALUA_GROUP_ID_B = 102

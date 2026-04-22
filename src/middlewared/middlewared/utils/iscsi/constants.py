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

# Relative target port ID (rel_tgt_id) assignment scheme for HA ALUA.
#
# Each target exposes one real TPG (tag = local node formula) and one phantom
# TPG (tag = remote node formula, no portals) on every node.  The phantom TPG
# carries no portals so initiators cannot connect through it, but its LUNs are
# assigned to the remote controller group so that a single RTPG response from
# any connected port lists both ALUA groups (controller_A and controller_B)
# with their correct states and relative port identifiers.
#
# TPG tag assignment:
#
#   Fabric              Node A tag                         Node B tag
#   ------------------  ---------------------------------  ------------------
#   iSCSI               rel_tgt_id                         rel_tgt_id + 32000
#   FC HBA M, target R  R + 5000 + Mx1000                  same + 32000
#
# iSCSI portal.tag values start at 1 and are unique per portal group.
# The FC base offset (5000) prevents collisions with iSCSI tags; the per-HBA
# multiplier (Mx1000) separates ports across HBAs on the same node.
# M is the numeric suffix of the HBA port name (fc0 -> 0, fc1 -> 1, fc1/2 -> 1).
#
# After failover the ALUA *state* of each group changes (ACTIVE_OPTIMIZED <->
# NONOPTIMIZED) but the TPG tags -- and therefore the relative port identifiers
# reported in RTPG -- remain stable.  Must match the SCST scst.conf.mako scheme.

# Node B adds this constant to every Node A tag to produce its own tag.
REL_TGT_ID_NODEB_OFFSET = 32000

# FC port tags start at this base to avoid collision with iSCSI portal tags.
REL_TGT_ID_FC_OFFSET = 5000

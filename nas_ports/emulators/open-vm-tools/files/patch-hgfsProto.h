--- lib/include/hgfsProto.h.orig
+++ lib/include/hgfsProto.h
@@ -148,6 +148,9 @@
    HGFS_OP_SET_EAS_V4,            /* Add or modify extended attributes. */
 
    HGFS_OP_MAX,                   /* Dummy op, must be last in enum */
+
+/* If a V4 packet is being processed as a legacy packet it will have this opcode. */
+   HGFS_V4_LEGACY_OPCODE = 0xff,
 } HgfsOp;
 
 
@@ -155,9 +158,6 @@
 #define HGFS_VERSION_OLD           (1 << 0)
 #define HGFS_VERSION_3             (1 << 1)
 
-/* If a V4 packet is being processed as a legacy packet it will have this opcode. */
-#define HGFS_V4_LEGACY_OPCODE      0xff
-
 /* XXX: Needs change when VMCI is supported. */
 #define HGFS_REQ_PAYLOAD_SIZE_V3(hgfsReq) (sizeof *hgfsReq + sizeof(HgfsRequest))
 #define HGFS_REP_PAYLOAD_SIZE_V3(hgfsRep) (sizeof *hgfsRep + sizeof(HgfsReply))

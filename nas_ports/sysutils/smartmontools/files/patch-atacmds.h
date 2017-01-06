--- atacmds.h.orig	2015-10-31 09:36:16.000000000 -0700
+++ atacmds.h	2016-06-15 19:39:43.425233000 -0700
@@ -74,7 +74,9 @@
 #define ATA_IDLE                        0xe3
 #define ATA_SMART_CMD                   0xb0
 #define ATA_SECURITY_FREEZE_LOCK        0xf5
+#ifndef ATA_SET_FEATURES
 #define ATA_SET_FEATURES                0xef
+#endif
 #define ATA_STANDBY_IMMEDIATE           0xe0
 
 // SET_FEATURES subcommands

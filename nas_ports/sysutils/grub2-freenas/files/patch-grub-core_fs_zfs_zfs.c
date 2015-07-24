--- grub-core/fs/zfs/zfs.c.orig	2014-08-06 10:04:26.129840841 -0400
+++ grub-core/fs/zfs/zfs.c	2014-08-06 10:05:01.587771419 -0400
@@ -281,7 +281,7 @@
  */
 #define MAX_SUPPORTED_FEATURE_STRLEN 50
 static const char *spa_feature_names[] = {
-  "org.illumos:lz4_compress",NULL
+  "org.illumos:lz4_compress","com.delphix:hole_birth","com.delphix:extensible_dataset","com.delphix:embedded_data",NULL
 };
 
 static int

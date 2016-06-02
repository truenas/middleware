--- grub-core/lib/libgcrypt/src/types.h.orig	2014-03-03 16:00:26 UTC
+++ grub-core/lib/libgcrypt/src/types.h
@@ -113,6 +113,8 @@
 #endif
 #endif
 
+typedef uint64_t u64;
+
 typedef union {
     int a;
     short b;

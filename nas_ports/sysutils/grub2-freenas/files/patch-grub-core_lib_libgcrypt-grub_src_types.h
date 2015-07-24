--- grub-core/lib/libgcrypt/src/types.h.o	2014-03-03 17:14:46.722210112 -0500
+++ grub-core/lib/libgcrypt/src/types.h	2014-03-03 17:05:54.572824164 -0500
@@ -113,6 +113,8 @@
 #endif
 #endif
 
+typedef uint64_t u64;
+
 typedef union {
     int a;
     short b;

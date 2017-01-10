--- lib/include/vm_basic_defs.h.orig	2013-09-23 15:51:10 UTC
+++ lib/include/vm_basic_defs.h
@@ -81,7 +81,11 @@
 #include "vm_basic_types.h" // For INLINE.
 
 /* Checks for FreeBSD, filtering out VMKERNEL. */
-#define __IS_FREEBSD__ (!defined(VMKERNEL) && defined(__FreeBSD__))
+#if !defined(VMKERNEL) && defined(__FreeBSD__)
+#define __IS_FREEBSD__ 1
+#else
+#define __IS_FREEBSD__ 0
+#endif
 #define __IS_FREEBSD_VER__(ver) (__IS_FREEBSD__ && __FreeBSD_version >= (ver))
 
 #if defined _WIN32 && defined USERLEVEL

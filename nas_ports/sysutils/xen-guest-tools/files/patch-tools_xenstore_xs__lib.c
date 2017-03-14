--- tools/xenstore/xs_lib.c.orig	2011-01-30 15:56:52.985324929 -0800
+++ tools/xenstore/xs_lib.c	2011-01-30 15:55:14.024346135 -0800
@@ -84,6 +84,8 @@
 	return "/proc/xen/xenbus";
 #elif defined(__NetBSD__)
 	return "/kern/xen/xenbus";
+#elif defined(__FreeBSD__)
+	return "/dev/xen/xenstore";
 #else
 	return "/dev/xen/xenbus";
 #endif

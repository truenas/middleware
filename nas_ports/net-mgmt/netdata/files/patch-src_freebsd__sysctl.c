--- src/freebsd_sysctl.c.orig	2017-03-20 18:26:59 UTC
+++ src/freebsd_sysctl.c
@@ -1,3 +1,8 @@
+#if __FreeBSD__ < 11 || __FreeBSD_version < 1100000
+#define _IFI_OQDROPS
+#define _IN_NET_RTSOCK_C
+#endif
+
 #include "common.h"
 
 #include <sys/vmmeter.h>

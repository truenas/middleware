--- etc/cnid_dbd/cnid_metad.c.orig	2011-07-30 18:28:32.000000000 -0400
+++ etc/cnid_dbd/cnid_metad.c	2011-07-30 18:29:01.000000000 -0400
@@ -39,6 +39,7 @@
 #include <string.h>
 #include <signal.h>
 #include <sys/types.h>
+#include <sys/resource.h>
 #include <sys/time.h>
 #include <sys/wait.h>
 #include <sys/uio.h>

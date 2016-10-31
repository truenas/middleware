--- etc/cnid_dbd/cnid_metad.c.orig	2016-06-06 11:21:51 UTC
+++ etc/cnid_dbd/cnid_metad.c
@@ -39,6 +39,7 @@
 #include <string.h>
 #include <signal.h>
 #include <sys/types.h>
+#include <sys/resource.h>
 #include <sys/time.h>
 #include <sys/resource.h>
 #include <sys/wait.h>

--- main.c.orig	2013-10-02 10:47:24.479295402 +0200
+++ main.c	2013-10-02 10:47:43.659318579 +0200
@@ -30,6 +30,7 @@
 #include <sys/sysctl.h>
 #endif
 
+extern int force_change;
 extern int dry_run;
 extern int list_only;
 extern int io_timeout;

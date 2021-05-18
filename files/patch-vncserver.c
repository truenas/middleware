--- vncserver.c.orig	2021-05-18 12:30:47.349796522 +0200
+++ vncserver.c	2021-05-18 12:31:45.968509449 +0200
@@ -28,6 +28,7 @@
  *
  */
 
+#include <arpa/inet.h>
 #include <stdio.h>
 #include <stdlib.h>
 #include <dlfcn.h>

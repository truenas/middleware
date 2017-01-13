--- src/modbus.c.orig	2016-01-22 09:51:17 UTC
+++ src/modbus.c
@@ -25,6 +25,9 @@
 #include "plugin.h"
 #include "configfile.h"
 
+/* FreeBSD needs this */
+#include <sys/socket.h> 
+
 #include <netdb.h>
 
 #include <modbus.h>

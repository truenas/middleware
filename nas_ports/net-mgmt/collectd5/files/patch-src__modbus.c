--- src/modbus.c.orig	2015-05-20 12:04:47 UTC
+++ src/modbus.c
@@ -25,6 +25,9 @@
 #include "plugin.h"
 #include "configfile.h"
 
+/* FreeBSD needs this */
+#include <sys/socket.h> 
+
 #include <netdb.h>
 
 #include <modbus/modbus.h>

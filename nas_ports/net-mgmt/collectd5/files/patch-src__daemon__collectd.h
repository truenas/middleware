--- src/daemon/collectd.h.orig	2016-01-22 09:51:17 UTC
+++ src/daemon/collectd.h
@@ -240,15 +240,15 @@ typedef int _Bool;
 #endif
 
 #ifndef LOCALSTATEDIR
-#define LOCALSTATEDIR PREFIX "/var"
+#define LOCALSTATEDIR "/var"
 #endif
 
 #ifndef PKGLOCALSTATEDIR
-#define PKGLOCALSTATEDIR PREFIX "/var/lib/" PACKAGE_NAME
+#define PKGLOCALSTATEDIR PREFIX "/var/db/" PACKAGE_NAME
 #endif
 
 #ifndef PIDFILE
-#define PIDFILE PREFIX "/var/run/" PACKAGE_NAME ".pid"
+#define PIDFILE "/var/run/" PACKAGE_NAME ".pid"
 #endif
 
 #ifndef PLUGINDIR

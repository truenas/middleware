--- src/daemon/collectd.h.orig	2016-12-05 23:16:57.702128468 -0500
+++ src/daemon/collectd.h	2016-12-05 23:18:17.932123583 -0500
@@ -243,15 +243,15 @@
 #endif
 
 #ifndef LOCALSTATEDIR
-# define LOCALSTATEDIR PREFIX "/var"
+# define LOCALSTATEDIR "/var"
 #endif
 
 #ifndef PKGLOCALSTATEDIR
-# define PKGLOCALSTATEDIR PREFIX "/var/lib/" PACKAGE_NAME
+# define PKGLOCALSTATEDIR PREFIX "/var/db/" PACKAGE_NAME
 #endif
 
 #ifndef PIDFILE
-# define PIDFILE PREFIX "/var/run/" PACKAGE_NAME ".pid"
+# define PIDFILE "/var/run/" PACKAGE_NAME ".pid"
 #endif
 
 #ifndef PLUGINDIR

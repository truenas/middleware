--- src/dyndns.h.orig	2014-06-01 08:01:18.000000000 -0700
+++ src/dyndns.h	2014-06-12 16:00:14.303836986 -0700
@@ -107,11 +107,11 @@
 
 /*test values*/
 #define DYNDNS_DEFAULT_DEBUG_LEVEL		LOG_WARNING
-#define DYNDNS_MT_DEFAULT_CONFIG_FILE_OLD	"/etc/inadyn-mt/inadyn-mt.conf"
-#define DYNDNS_MT_DEFAULT_CONFIG_FILE		"/etc/inadyn-mt.conf"
+#define DYNDNS_MT_DEFAULT_CONFIG_FILE_OLD	"%%PREFIX%%/etc/inadyn-mt/inadyn-mt.conf"
+#define DYNDNS_MT_DEFAULT_CONFIG_FILE		"%%PREFIX%%/etc/inadyn-mt.conf"
 
 /*inadyn backward compatibility*/
-#define DYNDNS_DEFAULT_CONFIG_FILE		"/etc/inadyn.conf"
+#define DYNDNS_DEFAULT_CONFIG_FILE		"%%PREFIX%%/etc/inadyn.conf"
 
 #define DYNDNS_DEFAULT_CACHE_PREFIX		"/tmp/"
 #define DYNDNS_DEFAULT_IP_FILE			"inadyn_ip.cache"

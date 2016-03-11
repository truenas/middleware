--- mDNSPosix/nss_mdns.c.orig
+++ mDNSPosix/nss_mdns.c
@@ -376,10 +376,23 @@
 errcode_t
 init_config ();
 
+static errcode_t __init_config ();
+
 #define ENTNAME  hostent
 #define DATABASE "hosts"
 
-#include <nss.h>
+#if defined __FreeBSD__
+# include <nsswitch.h>
+enum nss_status {
+  NSS_STATUS_SUCCESS = NS_SUCCESS,
+  NSS_STATUS_NOTFOUND = NS_NOTFOUND,
+  NSS_STATUS_UNAVAIL = NS_UNAVAIL,
+  NSS_STATUS_TRYAGAIN = NS_TRYAGAIN,
+  NSS_STATUS_RETURN = NS_RETURN
+};
+#elif defined __Linux__
+# include <nss.h>
+#endif
 // For nss_status
 #include <netdb.h>
 // For hostent
@@ -1684,7 +1697,7 @@
 //----------
 // Types and Constants
 
-const char * k_conf_file = "/etc/nss_mdns.conf";
+const char * k_conf_file = PREFIX"/etc/nss_mdns.conf";
 #define CONF_LINE_SIZE 1024
 
 const char k_comment_char = '#';
@@ -1792,6 +1805,12 @@
 errcode_t
 init_config ()
 {
+    return __init_config();
+}
+
+static errcode_t
+__init_config ()
+{
     if (g_config)
     {
         /*
@@ -1865,7 +1884,7 @@
 int
 config_is_mdns_suffix (const char * name)
 {
-    int errcode = init_config ();
+    int errcode = __init_config ();
     if (!errcode)
     {
         return contains_domain_suffix (g_config, name);

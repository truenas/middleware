--- lib/guestApp/guestApp.c.orig	2008-05-29 10:42:37.000000000 +0300
+++ lib/guestApp/guestApp.c	2008-05-29 10:43:09.000000000 +0300
@@ -65,7 +65,7 @@
 #elif defined __APPLE__
 #   define GUESTAPP_TOOLS_INSTALL_PATH "/Library/Application Support/VMware Tools"
 #else
-#   define GUESTAPP_TOOLS_INSTALL_PATH "/etc/vmware-tools"
+#   define GUESTAPP_TOOLS_INSTALL_PATH "/usr/local/share/vmware-tools"
 #endif
 
 /*

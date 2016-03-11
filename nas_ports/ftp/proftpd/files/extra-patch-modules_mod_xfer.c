--- modules/mod_xfer.c.org	Tue Jan  1 12:31:32 2008
+++ modules/mod_xfer.c	Tue Jan  1 16:45:20 2008
@@ -42,6 +42,8 @@
 #include <regex.h>
 #endif
 
+#include "mod_clamav.h"
+
 extern module auth_module;
 extern pid_t mpid;
 
@@ -1582,6 +1584,11 @@
       return PR_ERROR(cmd);
     }
 
+	if (clamav_scan(cmd)) {
+		pr_data_close(FALSE);
+		return PR_ERROR(cmd);
+	}
+	
     if (session.xfer.path &&
         session.xfer.path_hidden) {
       if (pr_fsio_rename(session.xfer.path_hidden, session.xfer.path) != 0) {

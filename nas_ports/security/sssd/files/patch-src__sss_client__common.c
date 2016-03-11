diff --git src/sss_client/common.c src/sss_client/common.c
index ec5c708..5d17eed 100644
--- src/sss_client/common.c
+++ src/sss_client/common.c
@@ -25,6 +25,7 @@
 #include "config.h"
 
 #include <nss.h>
+#include <nsswitch.h>
 #include <security/pam_modules.h>
 #include <errno.h>
 #include <sys/types.h>
@@ -43,6 +44,7 @@
 #include <libintl.h>
 #define _(STRING) dgettext (PACKAGE, STRING)
 #include "sss_cli.h"
+#include "util/sss_bsd_errno.h"
 
 #if HAVE_PTHREAD
 #include <pthread.h>
@@ -124,7 +126,6 @@ static enum sss_status sss_cli_send_req(enum sss_cli_command cmd,
             *errnop = error;
             break;
         case 0:
-            *errnop = ETIME;
             break;
         case 1:
             if (pfd.revents & (POLLERR | POLLHUP | POLLNVAL)) {
@@ -232,7 +233,6 @@ static enum sss_status sss_cli_recv_rep(enum sss_cli_command cmd,
             *errnop = error;
             break;
         case 0:
-            *errnop = ETIME;
             break;
         case 1:
             if (pfd.revents & (POLLHUP)) {
@@ -669,7 +669,6 @@ static enum sss_status sss_cli_check_socket(int *errnop, const char *socket_name
             *errnop = error;
             break;
         case 0:
-            *errnop = ETIME;
             break;
         case 1:
             if (pfd.revents & (POLLERR | POLLHUP | POLLNVAL)) {
@@ -719,23 +718,23 @@ enum nss_status sss_nss_make_request(enum sss_cli_command cmd,
     /* avoid looping in the nss daemon */
     envval = getenv("_SSS_LOOPS");
     if (envval && strcmp(envval, "NO") == 0) {
-        return NSS_STATUS_NOTFOUND;
+        return NS_NOTFOUND;
     }
 
     ret = sss_cli_check_socket(errnop, SSS_NSS_SOCKET_NAME);
     if (ret != SSS_STATUS_SUCCESS) {
-        return NSS_STATUS_UNAVAIL;
+        return NS_UNAVAIL;
     }
 
     ret = sss_cli_make_request_nochecks(cmd, rd, repbuf, replen, errnop);
     switch (ret) {
     case SSS_STATUS_TRYAGAIN:
-        return NSS_STATUS_TRYAGAIN;
+        return NS_TRYAGAIN;
     case SSS_STATUS_SUCCESS:
-        return NSS_STATUS_SUCCESS;
+        return NS_SUCCESS;
     case SSS_STATUS_UNAVAIL:
     default:
-        return NSS_STATUS_UNAVAIL;
+        return NS_UNAVAIL;
     }
 }
 

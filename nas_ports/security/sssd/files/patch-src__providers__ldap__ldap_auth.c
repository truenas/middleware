diff --git src/providers/ldap/ldap_auth.c src/providers/ldap/ldap_auth.c
index 2aacce0..e019cf7 100644
--- src/providers/ldap/ldap_auth.c
+++ src/providers/ldap/ldap_auth.c
@@ -37,7 +37,6 @@
 #include <sys/time.h>
 #include <strings.h>
 
-#include <shadow.h>
 #include <security/pam_modules.h>
 
 #include "util/util.h"
@@ -56,6 +55,22 @@ enum pwexpire {
     PWEXPIRE_SHADOW
 };
 
+struct spwd
+{
+  char *sp_namp;              /* Login name.  */
+  char *sp_pwdp;              /* Encrypted password.  */
+  long int sp_lstchg;         /* Date of last change.  */
+  long int sp_min;            /* Minimum number of days between changes.  */
+  long int sp_max;            /* Maximum number of days between changes.  */
+  long int sp_warn;           /* Number of days to warn user to change
+				 the password.  */
+  long int sp_inact;          /* Number of days the account may be
+				 inactive.  */
+  long int sp_expire;         /* Number of days since 1970-01-01 until
+				 account expires.  */
+  unsigned long int sp_flag;  /* Reserved.  */
+};
+
 static errno_t add_expired_warning(struct pam_data *pd, long exp_time)
 {
     int ret;
@@ -109,6 +124,7 @@ static errno_t check_pwexpire_kerberos(const char *expire_date, time_t now,
         return EINVAL;
     }
 
+    tzset();
     expire_time = mktime(&tm);
     if (expire_time == -1) {
         DEBUG(SSSDBG_CRIT_FAILURE,
@@ -116,12 +132,10 @@ static errno_t check_pwexpire_kerberos(const char *expire_date, time_t now,
         return EINVAL;
     }
 
-    tzset();
-    expire_time -= timezone;
     DEBUG(SSSDBG_TRACE_ALL,
-          "Time info: tzname[0] [%s] tzname[1] [%s] timezone [%ld] "
-           "daylight [%d] now [%ld] expire_time [%ld].\n", tzname[0],
-           tzname[1], timezone, daylight, now, expire_time);
+          "Time info: tzname[0] [%s] tzname[1] [%s] "
+          "now [%ld] expire_time [%ld].\n", tzname[0],
+          tzname[1], now, expire_time);
 
     if (difftime(now, expire_time) > 0.0) {
         DEBUG(SSSDBG_CONF_SETTINGS, "Kerberos password expired.\n");
@@ -924,7 +938,7 @@ void sdap_pam_chpass_handler(struct be_req *breq)
     DEBUG(SSSDBG_OP_FAILURE,
           "starting password change request for user [%s].\n", pd->user);
 
-    pd->pam_status = PAM_SYSTEM_ERR;
+    pd->pam_status = PAM_SERVICE_ERR;
 
     if (pd->cmd != SSS_PAM_CHAUTHTOK && pd->cmd != SSS_PAM_CHAUTHTOK_PRELIM) {
         DEBUG(SSSDBG_OP_FAILURE,
@@ -1069,7 +1083,7 @@ static void sdap_auth4chpass_done(struct tevent_req *req)
         dp_err = DP_ERR_OFFLINE;
         break;
     default:
-        state->pd->pam_status = PAM_SYSTEM_ERR;
+        state->pd->pam_status = PAM_SERVICE_ERR;
     }
 
 done:
@@ -1131,7 +1145,7 @@ static void sdap_pam_chpass_done(struct tevent_req *req)
                                                     state->sh, state->dn,
                                                     lastchanged_name);
         if (subreq == NULL) {
-            state->pd->pam_status = PAM_SYSTEM_ERR;
+            state->pd->pam_status = PAM_SERVICE_ERR;
             goto done;
         }
 
@@ -1152,7 +1166,7 @@ static void sdap_lastchange_done(struct tevent_req *req)
 
     ret = sdap_modify_shadow_lastchange_recv(req);
     if (ret != EOK) {
-        state->pd->pam_status = PAM_SYSTEM_ERR;
+        state->pd->pam_status = PAM_SERVICE_ERR;
         goto done;
     }
 
@@ -1193,7 +1207,7 @@ void sdap_pam_auth_handler(struct be_req *breq)
         goto done;
     }
 
-    pd->pam_status = PAM_SYSTEM_ERR;
+    pd->pam_status = PAM_SERVICE_ERR;
 
     switch (pd->cmd) {
     case SSS_PAM_AUTHENTICATE:
@@ -1291,7 +1305,7 @@ static void sdap_pam_auth_done(struct tevent_req *req)
         state->pd->pam_status = PAM_NEW_AUTHTOK_REQD;
         break;
     default:
-        state->pd->pam_status = PAM_SYSTEM_ERR;
+        state->pd->pam_status = PAM_SERVICE_ERR;
         dp_err = DP_ERR_FATAL;
     }
 

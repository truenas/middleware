diff --git src/providers/ldap/sdap_access.c src/providers/ldap/sdap_access.c
index 880735e..d349dcf 100644
--- src/providers/ldap/sdap_access.c
+++ src/providers/ldap/sdap_access.c
@@ -499,6 +499,7 @@ static bool nds_check_expired(const char *exp_time_str)
         return true;
     }
 
+    tzset();
     expire_time = mktime(&tm);
     if (expire_time == -1) {
         DEBUG(SSSDBG_CRIT_FAILURE,
@@ -506,13 +507,11 @@ static bool nds_check_expired(const char *exp_time_str)
         return true;
     }
 
-    tzset();
-    expire_time -= timezone;
     now = time(NULL);
     DEBUG(SSSDBG_TRACE_ALL,
-          "Time info: tzname[0] [%s] tzname[1] [%s] timezone [%ld] "
-           "daylight [%d] now [%ld] expire_time [%ld].\n", tzname[0],
-           tzname[1], timezone, daylight, now, expire_time);
+          "Time info: tzname[0] [%s] tzname[1] [%s] "
+          "now [%ld] expire_time [%ld].\n", tzname[0],
+          tzname[1], now, expire_time);
 
     if (difftime(now, expire_time) > 0.0) {
         DEBUG(SSSDBG_CONF_SETTINGS, "NDS account expired.\n");

--- ldap-grp.c.orig
+++ ldap-grp.c
@@ -687,7 +687,7 @@
   gid = strtoul (values[0], (char **) NULL, 10);
   ldap_value_free (values);
 
-  if (gid == LONG_MAX && errno == ERANGE)
+  if (gid == GID_MAX && errno == ERANGE)
     {
       /* invalid group, skip it */
       return NSS_NOTFOUND;

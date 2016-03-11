--- include/atalk/acl.h.orig	2014-07-28 11:01:46.000000000 -0400
+++ include/atalk/acl.h	2014-07-28 11:01:58.000000000 -0400
@@ -61,6 +61,7 @@ extern int remove_acl_vfs(const char *na
 #else /* HAVE_ACLS=no */
 
 #define O_NETATALK_ACL 0
+#define O_IGNORE 0
 #define chmod_acl chmod
 
 #endif /* HAVE_ACLS */

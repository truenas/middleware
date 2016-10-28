--- libatalk/vfs/extattr.c.orig	2016-06-22 08:57:37 UTC
+++ libatalk/vfs/extattr.c
@@ -194,6 +194,8 @@ ssize_t sys_fgetxattr (int filedes, cons
     const char *attrname = ((s=strchr(name, '.')) == NULL) ? name : s + 1;
 
     if((retval=extattr_get_fd(filedes, attrnamespace, attrname, NULL, 0)) >= 0) {
+        if (size == 0)
+            return retval;
         if(retval > size) {
             errno = ERANGE;
             return -1;

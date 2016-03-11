--- libatalk/vfs/extattr.c.orig	2014-06-03 01:40:44.000000000 -0400
+++ libatalk/vfs/extattr.c	2014-06-07 14:09:11.000000000 -0400
@@ -193,6 +193,8 @@ ssize_t sys_fgetxattr (int filedes, cons
     const char *attrname = ((s=strchr(name, '.')) == NULL) ? name : s + 1;
 
     if((retval=extattr_get_fd(filedes, attrnamespace, attrname, NULL, 0)) >= 0) {
+	if (size == 0)
+	    return retval;
         if(retval > size) {
             errno = ERANGE;
             return -1;

--- defs.pxd.orig	2017-09-10 04:00:05.369137000 +0200
+++ defs.pxd	2017-09-10 04:00:19.523758000 +0200
@@ -490,7 +490,7 @@
     char *EXTATTR_NAMESPACE_SYSTEM_STRING
     
     ssize_t extattr_get_fd(int fd, int attrnamespace, const char *attrname, void *data, size_t nbytes)
-    ssize_t exattr_set_fd(int fd, int attrnamespace, const char *attrname, const void *data, size_t nbytes)
+    ssize_t extattr_set_fd(int fd, int attrnamespace, const char *attrname, const void *data, size_t nbytes)
     int extattr_delete_fd(int fd, int attrnamespace, const char *attrname)
     ssize_t extattr_list_fd(int fd, int attrnamespace, void *data, size_t nbytes)
 

--- bsd/extattr.pyx.orig	2017-09-10 04:02:34.588468000 +0200
+++ bsd/extattr.pyx	2017-09-10 04:02:55.304263000 +0200
@@ -335,7 +335,7 @@
             if isinstance(fobj, file_types):
                 kr = defs.extattr_list_file(fobj.fileno(), namespace, data_buffer, nbytes)
             elif type(fobj) is int:
-                kr = defs.exattr_list_file(fobj, namespace, data_buffer, nbytes)
+                kr = defs.extattr_list_file(fobj, namespace, data_buffer, nbytes)
             elif type(fobj) is str:
                 if follow:
                     kr = defs.extattr_list_file(pname, namespace, data_buffer, nbytes)

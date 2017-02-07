--- ./buildtools/wafsamba/samba_install.py.orig	2015-08-09 19:55:47.819170736 +0000
+++ ./buildtools/wafsamba/samba_install.py	2015-08-09 19:56:18.727356203 +0000
@@ -116,7 +116,7 @@
                 inst_name    = bld.make_libname(t.target)
         elif self.vnum:
             vnum_base    = self.vnum.split('.')[0]
-            install_name = bld.make_libname(target_name, version=self.vnum)
+            install_name = bld.make_libname(target_name, version=vnum_base)
             install_link = bld.make_libname(target_name, version=vnum_base)
             inst_name    = bld.make_libname(t.target)
             if not self.private_library:
